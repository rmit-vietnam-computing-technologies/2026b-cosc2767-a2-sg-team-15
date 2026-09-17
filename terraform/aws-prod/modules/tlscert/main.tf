# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Bao Nguyen Pham Gia
# ID: s4143691
# Created  date: 8/09/2026
# Last modified: 16/09/2026
# Acknowledgement: HashiCorp terraform documentation and documentation for AWS provider (see root main.tf)

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
