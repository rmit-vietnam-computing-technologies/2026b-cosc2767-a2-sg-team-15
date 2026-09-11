terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    cloudflare = {
      source = "cloudflare/cloudflare"
      version = "~> 5"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

provider "cloudflare" {
  api_token = var.cf_api_token
}

module "vpc" {
  source = "./modules/vpc"
}

module "ec2" {
  source = "./modules/ec2"
  keypair_name = var.keypair_name
  vpc_id = module.vpc.vpc_id
  vpc_private_subnet_id = module.vpc.private_subnet_ids[0]
  vpc_public_subnet_id = module.vpc.public_subnet_id[0]
}

module "rds" {
  source = "./modules/rds"
  rds_username = var.db_username
  rds_password = var.db_password
  subnet_ids = module.vpc.private_subnet_ids
}

module "ecr" {
  source = "./modules/ecr"
}

module "tlscert" {
  source = "./modules/tlscert"
  domain_name = var.domain
  prod_record = var.prod_name
  api_record = var.api_name
}

resource "cloudflare_dns_record" "jenkins" {
  zone_id = var.zone_id
  # please do not the brainrot ehe~ the course code is COSC2767...
  name = "jenkins67"
  type = "A"
  content = module.ec2.jenkins_instance_public_ip
  ttl = 1
  proxied = false
  comment = "COSC2767 Jenkins Instance"
}

resource "cloudflare_dns_record" "prometheus" {
  zone_id = var.zone_id
  name = "prometheus67"
  type = "A"
  content = module.ec2.prometheus_public_ip
  ttl = 1
  proxied = false
  comment = "COSC2767 Prometheus Instance"
}

resource "cloudflare_dns_record" "prod_frontend" {
 zone_id = var.zone_id
 name = var.prod_name
 type = "A"
 # Confirm ALB settings before continuing
 content = "127.0.0.1"
 ttl = 1
 proxied = false
 comment = "COSC2767 Frontend ALB prod"
}

resource "cloudflare_dns_record" "api_frontend" {
 zone_id = var.zone_id
 name = var.api_name
 type = "A"
 # Confirm ALB settings before continuing
 content = "127.0.0.1"
 ttl = 1
 proxied = false
 comment = "COSC2767 API ALB"
}

resource "cloudflare_dns_record" "frontend_tls_validation" {
  for_each = {
    for dvo in module.tlscert.prod_cname_opts : dvo.domain_name => {
      name = dvo.resource_record_name
      type = dvo.resource_record_type
      content = dvo.resource_record_value
    }
  }

  zone_id = var.zone_id
  name = trimsuffix(each.value.name, ".")
  type = each.value.type
  content =  trimsuffix(each.value.content, ".")
  proxied = false
  ttl = 60
  comment = "COSC2767 Frontend TLS cert validation"
}

resource "cloudflare_dns_record" "api_tls_validation" {
  for_each = {
    for dvo in module.tlscert.api_cname_opts : dvo.domain_name => {
      name = dvo.resource_record_name
      type = dvo.resource_record_type
      content = dvo.resource_record_value
    }
  }

  zone_id = var.zone_id
  name = trimsuffix(each.value.name, ".")
  type = each.value.type
  content =  trimsuffix(each.value.content, ".")
  proxied = false
  ttl = 60
  comment = "COSC2767 api TLS cert validation"
}

resource "aws_acm_certificate_validation" "prod_validation" {
  certificate_arn = module.tlscert.prod_cert_arn
  validation_record_fqdns = [for record in cloudflare_dns_record.frontend_tls_validation : record.name]
}


resource "aws_acm_certificate_validation" "api_validation" {
  certificate_arn = module.tlscert.api_cert_arn
  validation_record_fqdns = [for record in cloudflare_dns_record.api_tls_validation : record.name]
}
