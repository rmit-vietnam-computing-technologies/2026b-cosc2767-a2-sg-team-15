# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 14/09/2026
# Last modified: 14/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author applied and
#   verified it. References: aws_ssm_parameter,
#   https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_parameter;
#   random_password, https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/password

# Application secrets, one set per environment, in SSM Parameter Store.
# deploy/bin/deploy.sh reads /rmit-store/<env>/* at deploy time, so no
# secret ever sits in a file on a laptop or a Jenkins agent.

resource "random_password" "django_secret" {
  for_each = toset(var.environments)
  length   = 64
  special  = false
}

resource "random_password" "seed_admin" {
  for_each = toset(var.environments)
  length   = 20
  special  = false
}

locals {
  app_parameters = merge([
    for env in var.environments : {
      "/rmit-store/${env}/SECRET_KEY" = {
        type  = "SecureString"
        value = random_password.django_secret[env].result
      }
      "/rmit-store/${env}/DATABASE_URL" = {
        type  = "SecureString"
        value = "postgres://${var.db_username}:${var.db_password}@${var.rds_host}:5432/rmit_${env}"
      }
      "/rmit-store/${env}/SEED_ADMIN_EMAIL" = {
        type  = "String"
        value = "admin@rmit.edu.au"
      }
      "/rmit-store/${env}/SEED_ADMIN_PASSWORD" = {
        type  = "SecureString"
        value = random_password.seed_admin[env].result
      }
    }
  ]...)
}

resource "aws_ssm_parameter" "app" {
  for_each = local.app_parameters

  name  = each.key
  type  = each.value.type
  value = each.value.value
}
