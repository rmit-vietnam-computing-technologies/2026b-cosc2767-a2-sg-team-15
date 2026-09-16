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
