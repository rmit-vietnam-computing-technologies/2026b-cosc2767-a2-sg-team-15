# What lies here is a hodge-podge of EKS configuration from two people,
# fused together as one, with few changes because some variables aren't there.
# Here be dragons. -giabao06

# Import the LabRole
import {
  identity = {
    name = "LabRole"
  }
  to = aws_iam_role.LabRole
}

resource "aws_iam_role" "LabRole" {
  # Left blank beacuse it's already imported
  lifecycle {
    prevent_destroy = true
  }
}

data "aws_eks_cluster_versions" "default" {
  cluster_type = "eks"
}

# terraform/eks-full-terraform/security_groups.tf
# Security group for the EKS cluster control plane
resource "aws_security_group" "eks_cluster_sg" {
  name        = "eks_cluster_sg"
  description = "Security group for EKS clusters"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Allow all internal traffic within the security group"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "eks_cluster_sg"
  }
}

# terraform/eks-full-terraform/eks.tf

# --- EKS control plane ---
resource "aws_eks_cluster" "prod_cluster" {
  name     = "prod_cluster"
  role_arn = data.aws_iam_role.lab_role.arn
  version  = data.aws_eks_cluster_versions.default[0].cluster_version

  vpc_config {
    subnet_ids              = var.subnet_ids
    security_group_ids      = [aws_security_group.eks_cluster_sg.id]
    endpoint_public_access  = true
    endpoint_private_access = false
  }

  bootstrap_self_managed_addons = false

  access_config {
    authentication_mode = "API_AND_CONFIG_MAP"
  }
}

resource "aws_eks_access_entry" "prod_LabRole_access_entry" {
  cluster_name  = aws_eks_cluster.prod_cluster.name
  principal_arn = data.aws_iam_role.LabRole.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "prod_cluster_admin" {
  cluster_name  = aws_eks_cluster.prod_cluster.name
  principal_arn = data.aws_iam_role.LabRole.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.lab_role]
}

resource "aws_eks_access_policy_association" "prod_admin" {
  cluster_name  = aws_eks_cluster.prod_cluster.name
  principal_arn = data.aws_iam_role.LabRole.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.prod_LabRole_access_entry]
}

resource "aws_eks_access_policy_association" "prod_edit" {
  cluster_name  = aws_eks_cluster.prod_cluster.name
  principal_arn = data.aws_iam_role.LabRole.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.prod_LabRole_access_entry]
}

resource "aws_eks_access_policy_association" "prod_view" {
  cluster_name  = aws_eks_cluster.prod_cluster.name
  principal_arn = data.aws_iam_role.LabRole.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.prod_LabRole_access_entry]
}

# --- Launch template for the node group ---
# We only set metadata_options and block_device_mappings here, deliberately
# leaving image_id and user_data unset. EKS auto-merges in the correct AMI
# and bootstrap script for a managed node group as long as those two fields
# are left blank - this is documented AWS behavior, not a workaround.
#
# The metadata_options block is the fix for a real issue we hit: the AWS
# Load Balancer Controller (and anything else needing node IAM credentials
# from inside a pod) couldn't reach the instance metadata service with the
# default hop limit of 1, since a pod's request counts as an extra network
# hop beyond the host's own namespace. Setting this to 2 here means every
# node launches with the fix already in place - no manual
# `aws ec2 modify-instance-metadata-options` needed after the fact.
resource "aws_launch_template" "node" {
  name_prefix = "eks-node-lt"
  key_name    = var.keypair_name

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 32
      volume_type = "gp3"
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 2
    http_tokens                 = "required"
  }

  vpc_security_group_ids = [aws_security_group.node_sg.id]

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "eks-node"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# --- Managed node group ---
resource "aws_eks_node_group" "prod_workers" {
  cluster_name    = aws_eks_cluster.prod_cluster.name
  node_group_name = "prod_node_group"
  node_role_arn   = data.aws_iam_role.LabRole.arn
  subnet_ids      = var.subnet_ids

  # There is no debian ami_type...
  ami_type       = "AL2023_x86_64_STANDARD"
  capacity_type  = "ON_DEMAND"
  instance_types = ["t3.medium"]

  launch_template {
    id      = aws_launch_template.node.id
    version = aws_launch_template.node.latest_version
  }

  scaling_config {
    desired_size = var.node_desired_size
    min_size     = var.node_min_size
    max_size     = var.node_max_size
  }

  depends_on = [
    aws_eks_access_policy_association.prod_cluster_admin,
  ]
}
