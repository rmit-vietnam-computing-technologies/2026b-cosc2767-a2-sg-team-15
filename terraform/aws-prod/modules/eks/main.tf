# What lies here is a hodge-podge of EKS configuration from two people,
# fused together as one, with few changes because some variables aren't there.
# Here be dragons. -giabao06

# Note: due to *the thing*, these are role-separated EKS clusters
# One cluster running both canary and production version of FE or BE.
#
# The ideal setup would be that one cluster run the one specific environment (env-separated clusters):
# One cluster running production version of BE AND FE, the other running Canary version.
# In this case, the Internet-facing ALB would try to RNG 5% then forward to the right cluster,
# but since it appears that I have to do some more
# AWS-vendor-lock-in-but-learner-lab-disallow stuff (mainly Route53 weighted routing),
# this is an accepted solution.

# Anyway why am I wandering into cloud engineering territory? This is Sys Deployment, not Cloud Architecting.

terraform {
  required_providers {
    kubernetes = {
      source                = "hashicorp/kubernetes"
      configuration_aliases = [kubernetes.frontend, kubernetes.backend]
    }
  }
}

# Import the LabRole
data "aws_iam_role" "LabRole" {
  name = "LabRole"
}


data "aws_eks_cluster_versions" "default" {
  cluster_type = "eks"
}

resource "kubernetes_config_map_v1_data" "frontend_auth" {
  provider = kubernetes.frontend
  metadata {
    name      = "aws-auth"
    namespace = "kube-system"
  }

  data = {
    mapRoles = yamlencode([
      {
        rolearn  = data.aws_iam_role.LabRole.arn
        username = "labrole-admin"
        groups   = ["system:masters"]
      }
    ])
  }

  force      = true
  depends_on = [aws_eks_cluster.frontend_cluster]
}

resource "kubernetes_config_map_v1_data" "backend_auth" {
  provider = kubernetes.backend
  metadata {
    name      = "aws-auth"
    namespace = "kube-system"
  }

  data = {
    mapRoles = yamlencode([
      {
        rolearn  = data.aws_iam_role.LabRole.arn
        username = "labrole-admin"
        groups   = ["system:masters"]
      }
    ])
  }

  force      = true
  depends_on = [aws_eks_cluster.backend_cluster]
}


# Frontend cluster, mostly taken from terraform/eks-full-terraform/security_groups.tf

# Security group for the EKS cluster control plane
resource "aws_security_group" "eks_cluster_sg" {
  name        = "eks_cluster_sg"
  description = "Security group for EKS clusters"
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow nodes to control plane API"
    from_port = 443
    to_port = 443
    protocol = "tcp"
    security_groups = [aws_security_group.node_sg.id]
  }
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
resource "aws_eks_cluster" "frontend_cluster" {
  name     = "frontend_cluster"
  role_arn = data.aws_iam_role.LabRole.arn
  version  = data.aws_eks_cluster_versions.default.cluster_versions[0].cluster_version

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


# Security group attached to worker nodes.
# Every rule here was something we discovered was missing through hands-on
# debugging - documented so nobody has to rediscover it:
#   - NodePort range: needed for the ELB (or ALB's target-type instance mode)
#     to reach services of type LoadBalancer / NodePort
#   - Port 80: needed for the ALB (target-type ip) to reach pods directly
#   - Port 22: needed for SSH troubleshooting (kubectl logs/exec is broken
#     by a separate kubelet TLS issue unrelated to security groups)
#   - Port 10250: control plane -> kubelet, needed for some cluster
#     management operations
resource "aws_security_group" "node_sg" {
  name        = "eks-node-sg"
  description = "Security group for EKS worker nodes"
  vpc_id      = var.vpc_id

  ingress {
    description = "NodePort range - needed for LoadBalancer/NodePort services"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Direct pod access for ALB target-type ip"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH for troubleshooting"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Control plane to kubelet"
    from_port   = 10250
    to_port     = 10250
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow all internal node-to-node traffic"
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
resource "aws_launch_template" "frontend_node" {
  name_prefix = "eks-node-lt-"
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

  vpc_security_group_ids = [
    aws_security_group.node_sg.id,
    aws_eks_cluster.frontend_cluster.vpc_config[0].cluster_security_group_id
  ]

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
resource "aws_eks_node_group" "fe_workers" {
  cluster_name    = aws_eks_cluster.frontend_cluster.name
  node_group_name = "fe_node_group"
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

}

# Backend cluster, taken from terraform/backend

# --- Control plane --------------------------------------------------------

resource "aws_eks_cluster" "backend_cluster" {
  name     = "backend_cluster"
  role_arn = data.aws_iam_role.LabRole.arn
  version  = data.aws_eks_cluster_versions.default.cluster_versions[0].cluster_version

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_public_access  = true
    endpoint_private_access = true
    security_group_ids = [aws_security_group.eks_cluster_sg.id]
  }

  # API mode from day one. Adding access_config to a live cluster forces a
  # replace in this provider, so it is never changed after creation. The
  # creator gets nothing automatically; the access entry below is the only
  # admin, and it is the lab session role, not one session of it.
  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = false
  }

  # Extended support is $0.60/h once a version ages out. Not for a lab.
  upgrade_policy {
    support_type = "STANDARD"
  }

  # tags = merge(local.tags, { Name = local.eks_name })

  lifecycle {
    # AWS moves the version on its own schedule; Terraform must never try to
    # move it back.
    ignore_changes = [version]

    precondition {
      condition     = length(var.subnet_ids) >= 2
      error_message = "EKS needs subnets in at least two AZs; check eks_azs against the VPC."
    }
  }
}


# --- Subnet tags for the cloud provider ----------------------------------

# type: LoadBalancer becomes a classic ELB. The controller finds subnets by
# these two tags and nothing else.
# resource "aws_ec2_tag" "eks_subnet_cluster" {
# for_each = toset(var.subnet_ids)

#  resource_id = each.value
#  key         = "kubernetes.io/cluster/backend_cluster"
#  value       = "shared"
#}

#resource "aws_ec2_tag" "eks_subnet_elb" {
#  for_each = toset(var.subnet_ids)
#
# resource_id = each.value
# key         = "kubernetes.io/role/elb"
#  value       = "1"
# }

# --- Nodes ----------------------------------------------------------------

# Exists so the RDS security group has something to allow. Not tagged with
# the cluster name on purpose: the cloud provider wants exactly one tagged
# SG per node when it wires an ELB, and EKS already tags the cluster SG.
resource "aws_security_group" "backend_eks_nodes" {

  name        = "backend_eks-nodes"
  description = "EKS nodes: handle for the RDS ingress rule"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge({ Name = "backend-eks-nodes" })
}

resource "aws_launch_template" "backend_nodes" {

  name_prefix = "backend-eks-node-"

  vpc_security_group_ids = [
    aws_eks_cluster.backend_cluster.vpc_config[0].cluster_security_group_id,
    aws_security_group.backend_eks_nodes.id,
  ]

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# instance_types stays here, not in the template: the two cannot both set it.
resource "aws_eks_node_group" "backend_workers" {
  cluster_name    = aws_eks_cluster.backend_cluster.name
  node_group_name = "backend-eks-nodes"
  node_role_arn   = data.aws_iam_role.LabRole.arn
  subnet_ids      = var.subnet_ids
  instance_types  = ["t3.medium"]
  ami_type        = "AL2023_x86_64_STANDARD"

  scaling_config {
    min_size     = var.node_min_size
    max_size     = var.node_max_size
    desired_size = var.node_desired_size
  }

  update_config {
    max_unavailable = 1
  }

  launch_template {
    id      = aws_launch_template.node.id
    version = aws_launch_template.node.latest_version
  }

  tags = merge({ Name = "backend-eks-nodes" })

  # Scaling to 0 before End Lab and back afterwards happens outside Terraform.
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

}
