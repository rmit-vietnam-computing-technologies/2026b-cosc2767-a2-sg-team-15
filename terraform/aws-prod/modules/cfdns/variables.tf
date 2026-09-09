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
