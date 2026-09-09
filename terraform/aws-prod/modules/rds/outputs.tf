output "prod_instance_endpoint" {
  description = "RDS instance endpoint for production instance"
  value = aws.db_instance.prod.endpoint
}

output "prod_instance_id" {
  description = "RDS Instance ID for production instance"
  value = aws.db_instance.prod.id
}

output "prod_instance_address" {
  description = "RDS Instance ID address for production"
  value = aws.db_instance.prod.address
}

output "canary_instance_endpoint" {
  description = "RDS instance endpoint for canary instance"
  value = aws.db_instance.canary.endpoint
}

output "canary_instance_id" {
  description = "RDS Instance ID for canary instance"
  value = aws.db_instance.canary.id
}

output "canary_instance_address" {
  description = "RDS Instance ID address for canary"
  value = aws.db_instance.canary.address
}
