resource "cloudflare_dns_record" "jenkins" {
  zone_id = var.cf_zone_id
  # please do not the brainrot ehe~ the course code is COSC2767...
  name = "jenkins67"
  type = "A"
  content = var.jenkins_instance_public_ip
  ttl = auto
  proxied = false
  comment = "COSC2767 Jenkins Instance"
}

resource "cloudflare_dns_record" "prod_frontend" {
  zone_id = var.cf_zone_id
  name = "aegleseeker"
  type = "A"
  content = var.frontend_alb_public_ip
  ttl = auto
  proxied = false
  comment = "COSC2767 Frontend ALB prod"
}

resource "cloudflare_dns_record" "canary_frontend" {
  zone_id = var.cf_zone_id
  name = "bagelseeker"
  type = "A"
  content = var.frontend_canary_alb_public_ip
  ttl = auto
  proxied = false
  comment = "COSC2767 Frontend ALB Canary"
}
