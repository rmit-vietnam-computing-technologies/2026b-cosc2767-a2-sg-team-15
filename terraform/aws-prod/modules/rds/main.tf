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
  publicly_accessible = false
  tags = {
    Name = "prod-rds"
  }
}
