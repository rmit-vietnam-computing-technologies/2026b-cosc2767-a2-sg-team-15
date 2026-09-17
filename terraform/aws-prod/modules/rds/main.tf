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

resource "aws_db_subnet_group" "main" {
  name = "prod-db-subnet-group"
  subnet_ids = var.subnet_ids
}

resource "aws_db_instance" "prod" {
  identifier = "rmitstore-prod"
  engine = "postgres"
  engine_version = "17"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  skip_final_snapshot = true
  username = var.rds_username
  password = var.rds_password
  multi_az = true
  db_subnet_group_name = aws_db_subnet_group.main.name
  publicly_accessible = false
  tags = {
    Name = "prod-rds"
  }
}
