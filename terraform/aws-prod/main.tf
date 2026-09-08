terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
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
