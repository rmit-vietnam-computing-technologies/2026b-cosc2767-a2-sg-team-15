# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Bao Nguyen Pham Gia
# ID: s4143691
# Created  date: 8/09/2026
# Last modified: 16/09/2026
# Acknowledgement: HashiCorp terraform documentation and documentation for AWS provider (see root main.tf)

output "vpc_id" {
  description = "The ID of the VPC"
  value = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "The ID of the public subnets"
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "The IDs of the private subnets"
  value = aws_subnet.private[*].id
}

output "igw_id" {
  description = "The ID of the Internet Gateway"
  value = aws_internet_gateway.igw1.id
}
