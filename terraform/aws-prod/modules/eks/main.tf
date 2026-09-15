# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 15/09/2026
# Last modified: 15/09/2026
# Acknowledgement: Rewrite of the first version by Bao Nguyen Pham Gia (giabao06),
#   which merged terraform/eks-full-terraform and terraform/backend. The cluster,
#   access entry, launch template and node group shape is lifted from
#   terraform/backend/eks.tf, where it is applied and verified. Drafted with
#   Claude (Anthropic); the author applied and verified it. References:
#   aws_eks_cluster, https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_cluster;
#   aws_eks_node_group, https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_node_group;
#   launch templates with managed node groups,
#   https://docs.aws.amazon.com/eks/latest/userguide/launch-templates.html;
#   access entries, https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html

# Two clusters, one per tier, built from the same set of resources with
# for_each. Both share the VPC's public subnets and the same node shape.
#
# Learner Lab shape:
#   - No iam:CreateRole, so LabRole is both the cluster role and the node role.
#   - No OIDC provider, so no IRSA. Pods get LabRole through the node's IMDS,
#     which is why the launch template sets the hop limit to 2.
#   - The lab session is an assumed role (voclabs). Only an explicit access
#     entry for that role gives kubectl a way in from any session.

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    # The root passes kubernetes.frontend and kubernetes.backend in. Nothing
    # here uses them: the aws-auth mapping they were for is shadowed by the
    # EC2_LINUX access entry the node group makes for LabRole, so it never
    # takes effect. Declared so the root wiring stays valid until it is
    # removed.
    kubernetes = {
      source                = "hashicorp/kubernetes"
      configuration_aliases = [kubernetes.frontend, kubernetes.backend]
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  lab_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"

  # arn:aws:sts::<acct>:assumed-role/voclabs/user123=name  ->  arn:aws:iam::<acct>:role/voclabs
  caller_role_name = try(regex("assumed-role/([^/]+)/", data.aws_caller_identity.current.arn)[0], null)
  admin_principal  = local.caller_role_name != null ? "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.caller_role_name}" : data.aws_caller_identity.current.arn

  # Keys are static (tier plus subnet index), so both maps are known at plan
  # time even while the VPC is still being created in the same apply. Keying
  # on the subnet ID breaks the plan with "known only after apply".
  subnet_pairs = {
    for p in setproduct(keys(var.cluster_names), range(length(var.subnet_ids))) :
    "${p[0]}/${p[1]}" => { cluster = p[0], subnet = var.subnet_ids[p[1]] }
  }
  subnets_by_index = { for i, id in var.subnet_ids : tostring(i) => id }
}

# --- Control planes -------------------------------------------------------

resource "aws_eks_cluster" "this" {
  for_each = var.cluster_names

  name     = each.value
  role_arn = local.lab_role_arn
  version  = var.eks_version

  # Private access on: nodes reach the API inside the VPC, so a subnet with
  # no internet route can still register. Public access stays on for kubectl.
  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_public_access  = true
    endpoint_private_access = true
    public_access_cidrs     = [var.admin_cidr]
  }

  # API mode. Adding access_config to a live cluster forces a replace in
  # this provider, so it is never changed after creation. The creator gets
  # nothing automatically; the access entry below is the only admin, and it
  # is the lab session role, not one session of it.
  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = false
  }

  # Extended support is $0.60/h once a version ages out. Not for a lab.
  upgrade_policy {
    support_type = "STANDARD"
  }

  tags = { Name = each.value }

  lifecycle {
    # AWS moves the version on its own schedule; Terraform must never try to
    # move it back.
    ignore_changes = [version]

    precondition {
      condition     = length(var.subnet_ids) >= 2
      error_message = "EKS needs subnets in at least two AZs."
    }
  }
}

# The lab session role gets cluster admin on both clusters. Sessions come
# and go; the role stays, so Jenkins and a laptop on the same lab credentials
# both get in.
resource "aws_eks_access_entry" "admin" {
  for_each = var.cluster_names

  cluster_name  = aws_eks_cluster.this[each.key].name
  principal_arn = local.admin_principal
  type          = "STANDARD"

  lifecycle {
    # The node group creates its own entry for LabRole; a second one for the
    # same ARN would collide. Run Terraform with lab CLI credentials, not
    # from an instance wearing LabRole.
    precondition {
      condition     = local.caller_role_name != "LabRole"
      error_message = "Apply from Learner Lab CLI credentials (voclabs), not from an instance profile."
    }
  }
}

resource "aws_eks_access_policy_association" "admin" {
  for_each = var.cluster_names

  cluster_name  = aws_eks_cluster.this[each.key].name
  principal_arn = aws_eks_access_entry.admin[each.key].principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

# --- Subnet tags for the cloud provider ----------------------------------

# type: LoadBalancer becomes a classic ELB. The controller finds subnets by
# these two tags and nothing else. Subnets are shared, so each carries one
# cluster tag per cluster. The subnets are Terraform-managed too, so the
# root aws provider ignores the kubernetes.io/ prefix; otherwise aws_subnet
# strips these on every apply and this puts them back, forever.
resource "aws_ec2_tag" "subnet_cluster" {
  for_each = local.subnet_pairs

  resource_id = each.value.subnet
  key         = "kubernetes.io/cluster/${var.cluster_names[each.value.cluster]}"
  value       = "shared"
}

resource "aws_ec2_tag" "subnet_elb" {
  for_each = local.subnets_by_index

  resource_id = each.value
  key         = "kubernetes.io/role/elb"
  value       = "1"
}

# --- Nodes ----------------------------------------------------------------

# Exists so the RDS security group has something to allow, plus SSH for
# poking at a node. Not tagged with the cluster name on purpose: the cloud
# provider wants exactly one tagged SG per node when it wires an ELB, and
# EKS already tags the cluster SG.
resource "aws_security_group" "nodes" {
  for_each = var.cluster_names

  name        = "${each.value}-nodes"
  description = "EKS nodes: handle for the RDS ingress rule, plus SSH"
  vpc_id      = var.vpc_id

  ingress {
    description = "SSH for troubleshooting"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${each.value}-nodes" }
}

# A custom launch template makes EKS stop attaching the cluster SG on its
# own, so it goes in here by hand. Without it the nodes and the control
# plane cannot talk. The template also fixes the IMDS hop limit: the EKS
# default template resets it to 1, which leaves pods with "no EC2 IMDS role
# found" and /readyz/ failing on storage.
resource "aws_launch_template" "nodes" {
  for_each = var.cluster_names

  name_prefix = "${each.value}-node-"
  key_name    = var.keypair_name

  vpc_security_group_ids = [
    aws_eks_cluster.this[each.key].vpc_config[0].cluster_security_group_id,
    aws_security_group.nodes[each.key].id,
  ]

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = var.node_disk_gb
      volume_type = "gp3"
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${each.value}-node" }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# instance_types stays here, not in the template: the two cannot both set it.
# No image_id and no user_data in the template either, so EKS merges in the
# right AMI and bootstrap for the cluster version.
resource "aws_eks_node_group" "this" {
  for_each = var.cluster_names

  cluster_name    = aws_eks_cluster.this[each.key].name
  node_group_name = "${each.value}-nodes"
  node_role_arn   = local.lab_role_arn
  subnet_ids      = var.subnet_ids
  instance_types  = [var.node_instance_type]
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
    id      = aws_launch_template.nodes[each.key].id
    version = aws_launch_template.nodes[each.key].latest_version
  }

  tags = { Name = "${each.value}-nodes" }

  # Scaling to 0 before End Lab and back afterwards happens outside Terraform.
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  depends_on = [aws_eks_access_policy_association.admin]
}
