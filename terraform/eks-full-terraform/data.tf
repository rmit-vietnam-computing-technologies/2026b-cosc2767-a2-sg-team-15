# AWS Academy Learner Lab pre-provisions this role. Terraform cannot create
# IAM roles in this environment, so we look it up instead of creating it.
data "aws_iam_role" "lab_role" {
  name = "LabRole"
}

data "aws_iam_instance_profile" "lab_instance_profile" {
  name = "LabInstanceProfile"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "cluster_subnets" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }

  filter {
    name   = "availability-zone"
    values = var.availability_zones
  }
}

data "aws_caller_identity" "current" {}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
