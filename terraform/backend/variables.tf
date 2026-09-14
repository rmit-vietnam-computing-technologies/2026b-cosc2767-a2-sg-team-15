# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 13/09/2026
# Last modified: 14/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author applied and
#   verified it. Reference: Terraform input variables,
#   https://developer.hashicorp.com/terraform/language/values/variables

variable "region" {
  description = "AWS region. Learner Lab lives in us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix for every resource name and tag."
  type        = string
  default     = "rmit-store"
}

variable "bucket_suffix" {
  description = "Bucket names are global; pick something unique like t15-260913."
  type        = string

  # S3 rejects uppercase and underscores, and the placeholder has both.
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,30}$", var.bucket_suffix))
    error_message = "bucket_suffix must be lowercase letters, digits and hyphens, e.g. t15-260913."
  }
}

variable "environments" {
  description = "One media bucket per entry."
  type        = list(string)
  default     = ["staging", "prod"]
}

# Leave both null to use the account's default VPC. Set both to land in the
# team VPC from terraform/aws-individual.
variable "vpc_id" {
  description = "VPC to build in. Null means the default VPC."
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "Subnets for the node and the RDS subnet group. Need two AZs. Null means every subnet in the VPC."
  type        = list(string)
  default     = null
}

variable "keypair_name" {
  description = "EC2 key pair for SSH. vockey is the Learner Lab one."
  type        = string
  default     = "vockey"
}

variable "node_instance_type" {
  description = "k3s node size. Two namespaces with two API replicas each want 4 GB."
  type        = string
  default     = "t3.medium"
}

variable "admin_cidr" {
  description = "Where SSH and the Kubernetes API are allowed from. Narrow it to your IP when you can."
  type        = string
  default     = "0.0.0.0/0"
}

variable "db_instance_class" {
  description = "RDS size. Smallest class the lab allows."
  type        = string
  default     = "db.t3.micro"
}

variable "db_username" {
  description = "RDS master user."
  type        = string
  default     = "rmit"
}

variable "db_password" {
  description = "RDS master password. Comes from terraform.tfvars or TF_VAR_db_password, never from git."
  type        = string
  sensitive   = true

  # RDS forbids / @ " and space; the placeholder must never reach an apply.
  validation {
    condition     = length(var.db_password) >= 8 && length(var.db_password) <= 41 && !can(regex("[/@\" ]|REPLACE", var.db_password))
    error_message = "db_password must be 8 to 41 chars, no / @ \" or space, and not the placeholder."
  }
}

# --- EKS, off by default ------------------------------------------------

variable "create_eks" {
  description = "Build the EKS cluster and node group from eks.tf. False leaves only the k3s node."
  type        = bool
  default     = false
}

variable "eks_version" {
  description = "Kubernetes version for the control plane. Null takes the EKS default; later drift is ignored either way."
  type        = string
  default     = null
}

variable "eks_azs" {
  description = "AZs whose subnets host the control plane and the nodes. Two or more, never us-east-1e."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.eks_azs) >= 2 && !contains(var.eks_azs, "us-east-1e")
    error_message = "eks_azs needs at least two zones and must not include us-east-1e, which EKS control planes cannot use."
  }
}

variable "eks_node_instance_type" {
  description = "Node size. Two of these plus the t3.medium stay well inside the lab's vCPU cap."
  type        = string
  default     = "t3.small"
}

variable "eks_node_min" {
  description = "Node group minimum and initial size."
  type        = number
  default     = 2
}

variable "eks_node_max" {
  description = "Node group maximum. Headroom for a rolling node replacement."
  type        = number
  default     = 3
}
