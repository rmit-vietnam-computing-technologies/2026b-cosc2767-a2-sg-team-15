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
