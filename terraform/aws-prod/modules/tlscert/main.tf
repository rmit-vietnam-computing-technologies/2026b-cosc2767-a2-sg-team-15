# Only provision AWS cert for the 2 frontend ELBs; the Jenkins will use Letsencrypt.
resource "aws_acm_certificate" "web-prod" {
  domain_name = "${var.prod_record}.${var.domain_name}"
  validation_method = "DNS"
  tags = {
    Name = "frontend-prod-cert"
  }
}

resource "aws_acm_certificate" "api-prod" {
  domain_name = "${var.api_record}.${var.domain_name}"
  validation_method = "DNS"
  tags = {
    Name = "api-prod-cert"
  }
}
