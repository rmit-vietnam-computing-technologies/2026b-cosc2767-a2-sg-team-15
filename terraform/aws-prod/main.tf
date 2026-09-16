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
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
  }
}

provider "aws" {
  region = "us-east-1"

  # The EKS module tags the subnets for the cloud provider with aws_ec2_tag.
  # Without this, aws_subnet strips those tags on every apply.
  ignore_tags {
    key_prefixes = ["kubernetes.io/"]
  }
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

module "ecr" {
  source = "./modules/ecr"
}

module "tlscert" {
  source = "./modules/tlscert"
  domain_name = var.domain
  prod_record = var.prod_name
  api_record = var.api_name
}

module "eks" {
 source = "./modules/eks"
 keypair_name = var.keypair_name
 subnet_ids = module.vpc.public_subnet_id
 vpc_id = module.vpc.vpc_id
}

resource "cloudflare_dns_record" "jenkins" {
  zone_id = var.zone_id
  # please do not the brainrot ehe~ the course code is COSC2767...
  name = var.jenkins_name
  type = "A"
  content = module.ec2.jenkins_instance_public_ip
  ttl = 1
  proxied = false
  comment = "COSC2767 Jenkins Instance"
}

resource "cloudflare_dns_record" "prometheus" {
  zone_id = var.zone_id
  name = var.prometheus_name
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

module "rds" {
  source = "./modules/rds"
  rds_username = var.db_username
  rds_password = var.db_password
  subnet_ids = module.vpc.private_subnet_ids
}

module "ssm" {
  source = "./modules/ssm"
  db_username = var.db_username
  db_password = var.db_password
  rds_host = module.rds.prod_instance_address
}
