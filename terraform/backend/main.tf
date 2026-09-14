# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 13/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author applied and
#   verified it. Bucket policy carried over from the Plan D rehearsal.
#   References: terraform_data,
#   https://developer.hashicorp.com/terraform/language/resources/terraform-data;
#   aws_db_instance,
#   https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance;
#   aws_instance metadata_options,
#   https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance#metadata-options

# Backend: one k3s node, one RDS Postgres, one media bucket
# per environment. Independent of terraform/aws-individual; point vpc_id and
# subnet_ids at that VPC to co-locate.

# --- Network  -------------------------------------------------

# Looked up unconditionally so no branch ever indexes an empty list.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "in_vpc" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

locals {
  vpc_id     = coalesce(var.vpc_id, data.aws_vpc.default.id)
  subnet_ids = var.subnet_ids != null ? var.subnet_ids : tolist(data.aws_subnets.in_vpc.ids)

  tags = {
    Project   = var.name_prefix
    ManagedBy = "terraform"
    Tier      = "backend"
  }
}

# --- Security groups -----------------------------------------------------

resource "aws_security_group" "node" {
  name        = "${var.name_prefix}-k3s-node"
  description = "k3s node: admin access from admin_cidr, HTTP from anywhere"
  vpc_id      = local.vpc_id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description = "Kubernetes API for kubectl"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description = "prod API"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "staging API"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${var.name_prefix}-k3s-node" })
}

resource "aws_security_group" "db" {
  name        = "${var.name_prefix}-rds"
  description = "Postgres from the k3s node only"
  vpc_id      = local.vpc_id

  ingress {
    description     = "Postgres from the node"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.node.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${var.name_prefix}-rds" })
}

# --- Database ------------------------------------------------------------

resource "aws_db_subnet_group" "db" {
  name       = "${var.name_prefix}-db"
  subnet_ids = local.subnet_ids
  tags       = local.tags
}

# One instance, two databases. rmit_staging is created here; rmit_prod is
# created from the node once psql is installed.
resource "aws_db_instance" "db" {
  identifier     = "${var.name_prefix}-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = "rmit_staging"
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.db.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true

  tags = local.tags
}

# --- Media buckets -------------------------------------------------------

# The Learner Lab SCP denies s3:GetBucketObjectLockConfiguration, which the
# aws_s3_bucket resource reads right after creating a bucket, so the create
# never completes. The CLI does the same three calls without that read.
# Idempotent: re-apply is safe, and destroy empties and removes the bucket.
resource "terraform_data" "media_bucket" {
  for_each = toset(var.environments)

  input            = "${var.name_prefix}-media-${each.key}-${var.bucket_suffix}"
  triggers_replace = ["${var.name_prefix}-media-${each.key}-${var.bucket_suffix}"]

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      B="${self.input}"
      aws s3api head-bucket --bucket "$B" 2>/dev/null \
        || aws s3api create-bucket --bucket "$B" --region ${var.region}
      aws s3api put-public-access-block --bucket "$B" --public-access-block-configuration \
        BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false
      aws s3api put-bucket-policy --bucket "$B" --policy \
        '{"Version":"2012-10-17","Statement":[{"Sid":"PublicReadMedia","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::'"$B"'/media/*"}]}'
    EOT
  }

  # Destroy provisioners cannot read variables, hence the literal region.
  provisioner "local-exec" {
    when        = destroy
    interpreter = ["bash", "-c"]
    command     = "aws s3 rb s3://${self.input} --force --region us-east-1 || true"
  }
}

# --- k3s node ------------------------------------------------------------

resource "aws_instance" "node" {
  ami                         = data.aws_ssm_parameter.al2023.insecure_value
  instance_type               = var.node_instance_type
  key_name                    = var.keypair_name
  subnet_id                   = local.subnet_ids[0]
  vpc_security_group_ids      = [aws_security_group.node.id]
  associate_public_ip_address = true

  # LabRole via the instance profile: pods reach S3 with no keys on disk.
  iam_instance_profile = "LabInstanceProfile"

  # Hop limit 2 so a pod behind the CNI bridge can still reach IMDS.
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  tags = merge(local.tags, { Name = "${var.name_prefix}-k3s-node" })
}

# Fixed address so kubeconfig, smoke URLs and the web tier survive a stop/start.
resource "aws_eip" "node" {
  domain = "vpc"
  tags   = merge(local.tags, { Name = "${var.name_prefix}-k3s-node" })
}

resource "aws_eip_association" "node" {
  instance_id   = aws_instance.node.id
  allocation_id = aws_eip.node.id
}
