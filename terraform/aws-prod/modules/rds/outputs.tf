output "prod_instance_endpoint" {
  description = "RDS instance endpoint for production instance"
  value = aws_db_instance.prod.endpoint
}

output "prod_instance_id" {
  description = "RDS Instance ID for production instance"
  value = aws_db_instance.prod.id
}

output "prod_instance_address" {
  description = "RDS Instance ID address for production"
  value = aws_db_instance.prod.address
}
