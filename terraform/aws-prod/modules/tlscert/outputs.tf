output "prod_cname_record" {
  description = "The CNAME record to set for Prod TLS cert validation"
  value = aws_acm_certificate.web-prod.domain_validation_options.resource_record_name
}

output "prod_cname_value" {
  description = "The CNAME value to set for Prod TLS cert validation"
  value = aws_acm_certificate.web-prod.domain_validation_options.resource_record_value
}

output "canary_cname_record" {
  description = "The CNAME record to set for canary TLS cert validation"
  value = aws_acm_certificate.web-canary.domain_validation_options.resource_record_name
}

output "canary_cname_value" {
  description = "The CNAME value to set for canary TLS cert validation"
  value = aws_acm_certificate.web-canary.domain_validation_options.resource_record_value
}
