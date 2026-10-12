# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Nguyen Bao Toan
# ID: s3926310
# Created  date: 05/09/2026
# Last modified: 17/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it again. References: https://registry.terraform.io/modules/lablabs/eks-load-balancer-controller/aws/latest

# We deliberately skip IRSA/OIDC here. A Learner Lab account can't create
# new IAM roles, so instead the controller pod borrows the worker node's
# own LabRole permissions via the EC2 instance metadata service (IMDS).
# This only works because the launch template above already sets the IMDS
# hop limit to 2 - without that, the controller fails at startup with
# "no EC2 IMDS role found" trying to reach the metadata service from a pod.
resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"

  set {
    name  = "clusterName"
    value = aws_eks_cluster.this.name
  }

  set {
    name  = "region"
    value = var.aws_region
  }

  set {
    name  = "vpcId"
    value = data.aws_vpc.default.id
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }

  depends_on = [
    aws_eks_node_group.devops_workers,
    aws_ec2_tag.public_subnet_elb,
  ]
}
