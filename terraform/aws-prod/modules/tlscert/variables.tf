variable "domain_name" {
  description = "The root domain name to provision AWS certs with"
  type = string
}

variable "prod_record" {
  description = "The DNS record for Production"
  type = string
}

variable "api_record" {
  description = "The DNS record for API server"
  type = string
}
