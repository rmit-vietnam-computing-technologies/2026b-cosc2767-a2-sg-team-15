variable "jenkins_instance_public_ip" {
  type = string
  description = "Public IP of Jenkins instance"
}

variable "zone_id" {
  type = string
  description = "ZoneID of Cloudflare"
}

variable "account_id" {
  type = string
  description = "Cloudflare Account ID"
}

variable "domain" {
  type = string
  description = "Cloudflare domain"
}
