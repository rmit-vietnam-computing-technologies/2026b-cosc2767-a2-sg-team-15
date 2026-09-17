# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Nguyen Bao Toan
# ID: s3926310
# Created  date: 05/09/2026
# Last modified: 17/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it again. References: https://developer.hashicorp.com/terraform/tutorials/aws-get-started/aws-create

variable "aws_region" {
  description = "AWS region (Learner Lab is us-east-1 only)"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "devops-eks-cluster"
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.30"
}

variable "availability_zones" {
  description = "AZs to deploy the cluster and node group into"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "node_group_name" {
  description = "Name of the managed node group"
  type        = string
  default     = "devops-workers-group"
}

variable "node_instance_types" {
  description = "EC2 instance types for the worker nodes"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_disk_size" {
  description = "Root volume size (GiB) for worker nodes"
  type        = number
  default     = 20
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 2
}

variable "key_pair_name" {
  description = "Name of an EXISTING EC2 key pair (Learner Lab accounts can't create IAM but CAN create key pairs - create this one first if it doesn't exist)"
  type        = string
  default     = "devops_project_key"
}

variable "eksctl_instance_name" {
  type    = string
  default = "eksctl_kubectl_server"
}

variable "eksctl_instance_type" {
  type    = string
  default = "t3.micro"
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository holding the frontend image"
  type        = string
  default     = "webapp-frontend-terraform"
}

variable "frontend_image" {
  description = "Full ECR image URI for the production frontend, e.g. <account-id>.dkr.ecr.us-east-1.amazonaws.com/webapp-frontend:latest"
  type        = string
}

variable "frontend_canary_image" {
  description = "Full ECR image URI for the canary frontend, e.g. <account-id>.dkr.ecr.us-east-1.amazonaws.com/webapp-frontend:canary"
  type        = string
}

variable "frontend_container_port" {
  description = "Port the frontend app actually listens on inside the container"
  type        = number
  default     = 80
}

variable "frontend_replicas" {
  type    = number
  default = 3
}

variable "canary_replicas" {
  type    = number
  default = 1
}

variable "canary_weight" {
  description = "Percentage of traffic (0-100) sent to the canary target group"
  type        = number
  default     = 10
}
