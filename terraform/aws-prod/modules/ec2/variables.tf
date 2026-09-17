# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Bao Nguyen Pham Gia
# ID: s4143691
# Created  date: 8/09/2026
# Last modified: 16/09/2026
# Acknowledgement: HashiCorp terraform documentation and documentation for AWS provider (see root main.tf)
#
variable "keypair_name" {
  description = "The name of the Keypair that will be applied to **EVERY** ec2 instance"
  type = string
}

variable "vpc_public_subnet_id" {
  description = "The subnetID of the VPC where the EC2 instance will be located"
  type = string
}

variable "vpc_private_subnet_id" {
  description = "The SubnetID of the private VPC where the EC2 instance will be located"
  type = string
}

variable "vpc_id" {
  description = "The ID of the VPC"
  type = string
}
