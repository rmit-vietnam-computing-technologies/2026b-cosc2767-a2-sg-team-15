# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Bao Nguyen Pham Gia
# ID: s4143691
# Created  date: 8/09/2026
# Last modified: 16/09/2026
# Acknowledgement: HashiCorp terraform documentation and documentation for AWS provider (see root main.tf)

output "frontend_ecr_repo_id" {
  description = "ID of the ECR repo"
  value = aws_ecr_repository.frontend_ecr_repo.id
}

output "frontend_ecr_repo_url" {
  description = "URL of the ECR repo"
  value = aws_ecr_repository.frontend_ecr_repo.repository_url
}

output "backend_ecr_repo_id" {
  description = "ID of the ECR repo"
  value = aws_ecr_repository.frontend_ecr_repo.id
}

output "backend_ecr_repo_url" {
  description = "URL of the ECR repo"
  value = aws_ecr_repository.backend_ecr_repo.repository_url
}
