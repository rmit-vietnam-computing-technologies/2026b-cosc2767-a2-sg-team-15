variable "domain_name" {
  description = "The root domain name to provision AWS certs with"
  type = string
}

variable "prod_record" {
  description = "The DNS record for Production"
  type = string
}

variable "canary_record" {
  description = "The DNS record for Canary"
  type = string
}
