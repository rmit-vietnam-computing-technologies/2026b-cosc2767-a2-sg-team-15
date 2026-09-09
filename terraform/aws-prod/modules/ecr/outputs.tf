output "ecr_repo_id" {
  description = "ID of the ECR repo"
  value = aws_ecr_repository.ecr_repo.id
}

output "ecr_repo_url" {
  description = "URL of the ECR repo"
  value = aws_ecr_repository.ecr_repo.repository_url
}
