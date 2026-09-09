resource "aws_ecr_repository" "ecr_repo" {
  name = "main_ecr"

  image_scanning_configuration {
    scan_on_push = true
  }
}
