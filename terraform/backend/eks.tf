# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 14/09/2026
# Last modified: 14/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author applied and
#   verified it. References: aws_eks_cluster,
#   https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_cluster;
#   aws_eks_node_group,
#   https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_node_group;
#   EKS access entries, https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html;
#   LabRole as cluster and node role follows a public Learner Lab precedent,
#   https://github.com/PedrosPinho/soat15-tech-challenge-k8s-infra

# EKS, behind create_eks. A plain apply never builds it; -var create_eks=true
# adds a cluster and a two-node group next to the k3s node, sharing the same
# RDS, buckets and SSM parameters. The manifests in deploy/k8s and the scripts
# in deploy/bin do not know which cluster they talk to.
#
# Learner Lab shape:
#   - No iam:CreateRole, so LabRole is both the cluster role and the node role.
#   - No OIDC provider, so no IRSA. Pods get LabRole through the node's IMDS,
#     which is why the launch template sets the hop limit to 2.
#   - The lab session is an assumed role (voclabs). Only an explicit access
#     entry for that role gives kubectl a way in from any session.
#   - Control plane is about $0.10/h, plus two t3.small and one classic ELB
#     per namespace. Scale the node group to 0 before End Lab.

data "aws_caller_identity" "current" {}

data "aws_subnets" "eks" {
  count = var.create_eks ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  # us-east-1e never makes this list: EKS will not place a control plane there.
  filter {
    name   = "availability-zone"
    values = var.eks_azs
  }
}

locals {
  eks_name     = "${var.name_prefix}-eks"
  lab_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"

  # arn:aws:sts::<acct>:assumed-role/voclabs/user123=name  ->  arn:aws:iam::<acct>:role/voclabs
  caller_role_name = try(regex("assumed-role/([^/]+)/", data.aws_caller_identity.current.arn)[0], null)
  admin_principal  = local.caller_role_name != null ? "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.caller_role_name}" : data.aws_caller_identity.current.arn

  # flatten over the splat: an empty list when the data source has count 0.
  eks_subnet_ids = flatten(data.aws_subnets.eks[*].ids)
}

# --- Control plane --------------------------------------------------------

resource "aws_eks_cluster" "this" {
  count = var.create_eks ? 1 : 0

  name     = local.eks_name
  role_arn = local.lab_role_arn
  version  = var.eks_version

  vpc_config {
    subnet_ids              = local.eks_subnet_ids
    endpoint_public_access  = true
    endpoint_private_access = true
    public_access_cidrs     = [var.admin_cidr]
  }

  # API mode. Adding access_config to a live cluster forces a
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

  tags = merge(local.tags, { Name = local.eks_name })

  lifecycle {
    # AWS moves the version on its own schedule; Terraform must never try to
    # move it back.
    ignore_changes = [version]

    precondition {
      condition     = length(local.eks_subnet_ids) >= 2
      error_message = "EKS needs subnets in at least two AZs; check eks_azs against the VPC."
    }
  }
}

# The lab session role gets cluster admin. Sessions come and go; the role
# stays, so Jenkins and a laptop on the same lab credentials both get in.
resource "aws_eks_access_entry" "admin" {
  count = var.create_eks ? 1 : 0

  cluster_name  = aws_eks_cluster.this[0].name
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
  count = var.create_eks ? 1 : 0

  cluster_name  = aws_eks_cluster.this[0].name
  principal_arn = aws_eks_access_entry.admin[0].principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

# --- Subnet tags for the cloud provider ----------------------------------

# type: LoadBalancer becomes a classic ELB. The controller finds subnets by
# these two tags and nothing else.
resource "aws_ec2_tag" "eks_subnet_cluster" {
  for_each = toset(local.eks_subnet_ids)

  resource_id = each.value
  key         = "kubernetes.io/cluster/${local.eks_name}"
  value       = "shared"
}

resource "aws_ec2_tag" "eks_subnet_elb" {
  for_each = toset(local.eks_subnet_ids)

  resource_id = each.value
  key         = "kubernetes.io/role/elb"
  value       = "1"
}

# --- Nodes ----------------------------------------------------------------

# Exists so the RDS security group has something to allow. Not tagged with
# the cluster name on purpose: the cloud provider wants exactly one tagged
# SG per node when it wires an ELB, and EKS already tags the cluster SG.
resource "aws_security_group" "eks_nodes" {
  count = var.create_eks ? 1 : 0

  name        = "${var.name_prefix}-eks-nodes"
  description = "EKS nodes: handle for the RDS ingress rule"
  vpc_id      = local.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${var.name_prefix}-eks-nodes" })
}

# Two reasons for a launch template: the extra security group above, and the
# IMDS hop limit. A custom template resets the hop limit to 1, which leaves
# pods with "no EC2 IMDS role found" and /readyz/ failing on storage.
resource "aws_launch_template" "eks_nodes" {
  count = var.create_eks ? 1 : 0

  name_prefix = "${var.name_prefix}-eks-node-"

  vpc_security_group_ids = [
    aws_eks_cluster.this[0].vpc_config[0].cluster_security_group_id,
    aws_security_group.eks_nodes[0].id,
  ]

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.tags, { Name = "${var.name_prefix}-eks-node" })
  }

  lifecycle {
    create_before_destroy = true
  }
}

# instance_types stays here, not in the template: the two cannot both set it.
resource "aws_eks_node_group" "this" {
  count = var.create_eks ? 1 : 0

  cluster_name    = aws_eks_cluster.this[0].name
  node_group_name = "${var.name_prefix}-eks-nodes"
  node_role_arn   = local.lab_role_arn
  subnet_ids      = local.eks_subnet_ids
  instance_types  = [var.eks_node_instance_type]
  ami_type        = "AL2023_x86_64_STANDARD"

  scaling_config {
    min_size     = var.eks_node_min
    max_size     = var.eks_node_max
    desired_size = var.eks_node_min
  }

  update_config {
    max_unavailable = 1
  }

  launch_template {
    id      = aws_launch_template.eks_nodes[0].id
    version = aws_launch_template.eks_nodes[0].latest_version
  }

  tags = merge(local.tags, { Name = "${var.name_prefix}-eks-nodes" })

  # Scaling to 0 before End Lab and back afterwards happens outside Terraform.
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  depends_on = [aws_eks_access_policy_association.admin]
}
