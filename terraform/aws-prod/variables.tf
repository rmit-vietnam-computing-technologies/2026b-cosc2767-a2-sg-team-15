variable "keypair_name" {
  description = "The name of the Keypair that will be applied to **EVERY** ec2 instance"
  type = string
}

variable "private_key_path" {
  description = "Path to ssh private key of the keypair"
  type = string
}

variable "cf_api_token" {
  description = "The Cloudflare API token"
  type = string
}

variable "account_id" {
  description = "The Cloudflare Account ID"
  type = string
}

variable "domain" {
  description = "The cloudflare domain to set DNS on"
  type = string
}

variable "prod_name" {
  description = "The DNs name for prod"
  type = string
}

variable "jenkins_name" {
  description = "The DNs name for jenkins"
  type = string
}

variable "prometheus_name" {
  description = "The DNs name for prometheus"
  type = string
}

variable "api_name" {
  description = "The DNS name for api"
  type = string
}

variable "zone_id" {
  description = "The cloudflare zoneid"
  type = string
}

variable "db_username" {
  description = "Database username to set"
  type = string
}

variable "db_password" {
  description = "Database password to set"
  type = string
}

variable "letsenc_email" {
  description = "Let's encrypt email"
  type = string
}
