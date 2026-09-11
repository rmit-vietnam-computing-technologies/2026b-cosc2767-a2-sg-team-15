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

module "tlscert" {
  source = "./modules/tlscert"
  domain_name = var.domain
  prod_record = var.prod_name
  canary_record = var.canary_name
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

resource "cloudflare_dns_record" "prod_frontend" {
 zone_id = var.zone_id
 name = "aegleseeker"
 type = "A"
 # Confirm ALB settings before continuing
 content = "127.0.0.1"
 ttl = auto
 proxied = false
 comment = "COSC2767 Frontend ALB prod"
}

resource "cloudflare_dns_record" "canary_frontend" {
 zone_id = var.zone_id
 name = "bagelseeker"
 type = "A"
 # Confirm ALB settings before continuing
 content = "127.0.0.1"
 ttl = auto
 proxied = false
 comment = "COSC2767 Frontend ALB Canary"
}

resource "cloudflare_dns_record" "frontend_tls_validation" {
  zone_id = var.zone_id
  name = module.tlscert.prod_cname_record
  type = "CNAME"
  content = module.tlscert.prod_cname_value
  proxied = false
  ttl = auto
  comment = "COSC2767 Frontend TLS cert validation"
}

resource "cloudflare_dns_record" "frontend_canary_tls_validation" {
  zone_id = var.zone_id
  name = module.tlscert.canary_cname_record
  type = "CNAME"
  content = module.tlscert.canary_cname_value
  proxied = false
  ttl = auto
  comment = "COSC2767 Frontend Canary TLS cert validation"
}
