resource "aws_ecr_repository" "frontend_ecr_repo" {
  name = "frontend_ecr"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "backend_ecr_repo" {
  name = "backend_ecr"

  image_scanning_configuration {
    scan_on_push = true
  }
}
