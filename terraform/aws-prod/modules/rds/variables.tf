# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Bao Nguyen Pham Gia
# ID: s4143691
# Created  date: 8/09/2026
# Last modified: 16/09/2026
# Acknowledgement: HashiCorp terraform documentation and documentation for AWS provider (see root main.tf)
# Not used due to Learner lab permissions

variable "subnet_ids" {
  description = "The subnet ids for the RDS database"
  type = list(string)
}


variable "rds_username" {
  description = "RDS username"
  type = string
}

variable "rds_password" {
  description = "RDS password"
  type = string
}
