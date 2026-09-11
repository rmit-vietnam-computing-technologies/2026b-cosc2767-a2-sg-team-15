output "prod_cert_arn" {
  description = "The ARN of the production certificate"
  value = aws_acm_certificate.web-prod.arn
}

output "prod_cname_opts" {
  description = "The CNAME options to set for Prod TLS cert validation"
  value = aws_acm_certificate.web-prod.domain_validation_options
}

output "canary_cert_arn" {
  description = "The ARN of the canary certificate"
  value = aws_acm_certificate.web-canary.arn
}

output "canary_cname_opts" {
  description = "The CNAME option to set for canary TLS cert validation"
  value = aws_acm_certificate.web-canary.domain_validation_options
}
