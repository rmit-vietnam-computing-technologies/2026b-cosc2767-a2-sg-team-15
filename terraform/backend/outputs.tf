# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 13/09/2026
# Last modified: 14/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author applied and
#   verified it. Reference: Terraform output values,
#   https://developer.hashicorp.com/terraform/language/values/outputs

# What Ansible, the deploy script and the smoke suite need from this stack.

output "node_public_ip" {
  description = "Elastic IP of the k3s node. SSH, kubectl, and the API URLs."
  value       = aws_eip.node.public_ip
}

output "node_private_ip" {
  description = "Private IP of the k3s node, for the web tier's proxy."
  value       = aws_instance.node.private_ip
}

output "node_security_group_id" {
  description = "Attach further ingress here, e.g. from the Jenkins agent."
  value       = aws_security_group.node.id
}

output "rds_endpoint" {
  description = "RDS hostname. Reachable from the node only."
  value       = aws_db_instance.db.address
}

output "media_buckets" {
  description = "Bucket name per environment."
  value       = { for env, b in terraform_data.media_bucket : env => b.output }
}

output "database_url_staging" {
  description = "DATABASE_URL for the staging namespace."
  value       = "postgres://${var.db_username}:${var.db_password}@${aws_db_instance.db.address}:5432/rmit_staging"
  sensitive   = true
}

output "database_url_prod" {
  description = "DATABASE_URL for the prod namespace. The database itself is created from the node."
  value       = "postgres://${var.db_username}:${var.db_password}@${aws_db_instance.db.address}:5432/rmit_prod"
  sensitive   = true
}

output "ssm_parameter_paths" {
  description = "Where deploy.sh reads each environment's secrets from."
  value       = { for env in var.environments : env => "/${var.name_prefix}/${env}" }
}
