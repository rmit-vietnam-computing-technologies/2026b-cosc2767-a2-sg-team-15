variable "jenkins_instance_public_ip" {
  type = string
  description = "Public IP of Jenkins instance"
}

variable "frontend_alb_public_ip" {
  type = string
  description = "Public IP of frontend ALB"
}

variable "frontend_canary_alb_public_ip" {
  type = string
  description = "Public IP of Canary Frontend ALB"
}

variable "cf_zone_id" {
  description = "The cloudflare zoneid"
  type = string
}

variable "frontend_prod_cname_record" {
  description = "CNAME Record for Frontend TLS cert domain name validation"
  type = string
}

variable "frontend_prod_cname_value" {
  description = "CNAME value for Frontend TLS cert domain name validation"
  type = string
}

variable "frontend_canary_cname_record" {
  description = "CNAME Record for Frontend canary TLS cert domain name validation"
  type = string
}

variable "frontend_canary_cname_value" {
  description = "CNAME value for Frontend canary TLS cert domain name validation"
  type = string
}
