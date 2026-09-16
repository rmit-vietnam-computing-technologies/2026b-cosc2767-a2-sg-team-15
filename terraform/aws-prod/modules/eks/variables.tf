# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 15/09/2026
# Last modified: 15/09/2026
# Acknowledgement: Extends the variables from the first version by
#   Bao Nguyen Pham Gia (giabao06). Drafted with Claude (Anthropic); the author
#   applied and verified it. Reference: Terraform input variables,
#   https://developer.hashicorp.com/terraform/language/values/variables

variable "vpc_id" {
  description = "VPC that holds the clusters and the nodes."
  type        = string
}

variable "subnet_ids" {
  description = "Subnets for the control planes and the nodes. Two or more AZs, every one with a route to the internet gateway."
  type        = list(string)
}

variable "keypair_name" {
  description = "Key pair baked into the node launch templates, for SSH troubleshooting."
  type        = string
}

# New knobs. Defaults keep Bao's cluster names and node size.

variable "cluster_names" {
  description = "Cluster name per tier. Keys are stable handles, values are the EKS names. Set backend to match the name in webapp/Jenkinsfile."
  type        = map(string)
  default = {
    frontend = "frontend_cluster"
    backend  = "backend_cluster"
  }
}

variable "eks_version" {
  description = "Kubernetes version for the control planes. Null takes the EKS default; later drift is ignored either way."
  type        = string
  default     = null
}

variable "admin_cidr" {
  description = "Who may reach the public API endpoints and SSH to the nodes. Tighten to your own /32 when the lab allows."
  type        = string
  default     = "0.0.0.0/0"
}

variable "node_instance_type" {
  description = "Node size. Four of these across two clusters stay inside the lab's vCPU cap."
  type        = string
  default     = "t3.medium"
}

variable "node_disk_gb" {
  description = "Root volume per node, gp3."
  type        = number
  default     = 32
}

variable "node_desired_size" {
  description = "Initial node count per cluster."
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Node group minimum per cluster."
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Node group maximum per cluster. Headroom for a rolling node replacement."
  type        = number
  default     = 3
}
