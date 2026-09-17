# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Bao Nguyen Pham Gia
# ID: s4143691
# Created  date: 8/09/2026
# Last modified: 16/09/2026
# Acknowledgement: HashiCorp terraform documentation and documentation for AWS provider (see root main.tf)

output "prod_cert_arn" {
  description = "The ARN of the production certificate"
  value = aws_acm_certificate.web-prod.arn
}

output "api_cert_arn" {
  description = "The ARN of the api certificate"
  value = aws_acm_certificate.api-prod.arn
}

output "prod_cname_opts" {
  description = "The CNAME options to set for Prod TLS cert validation"
  value = aws_acm_certificate.web-prod.domain_validation_options
}

output "api_cname_opts" {
  description = "The CNAME options to set for API TLS cert validation"
  value = aws_acm_certificate.api-prod.domain_validation_options
}
