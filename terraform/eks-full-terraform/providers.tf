# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Nguyen Bao Toan
# ID: s3926310
# Created  date: 05/09/2026
# Last modified: 17/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it again. References: https://registry.terraform.io/providers/hashicorp/helm/latest/docs

provider "aws" {
  region = var.aws_region
}

# Kubernetes and Helm providers authenticate against the cluster we create
# below, using a short-lived auth token - this is the same mechanism
# `aws eks update-kubeconfig` sets up for kubectl.
data "aws_eks_cluster_auth" "this" {
  name = aws_eks_cluster.this.name
}

provider "kubernetes" {
  host                   = aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(aws_eks_cluster.this.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.this.token
}

provider "helm" {
  kubernetes {
    host                   = aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(aws_eks_cluster.this.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}
