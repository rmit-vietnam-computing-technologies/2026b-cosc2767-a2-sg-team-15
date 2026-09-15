variable "subnet_ids" {
  description = "The Subnet IDS to place EKS clusters in"
  type = list(string)
}

variable "keypair_name" {
  description = "The name of the Keypair that will be applied to **EVERY** ec2 instance"
  type = string
}

variable "node_desired_size" {
  description = "Desired number of nodes to scale"
  type    = number
  default = 2
}

variable "node_min_size" {
  description = "Minimum number of nodes to scale"
  type    = number
  default = 2
}

variable "node_max_size" {
  description = "Maximum number of nodes to scale"
  type    = number
  default = 2
}

variable "vpc_id" {
  description = "VPC ID"
  type = string
}
