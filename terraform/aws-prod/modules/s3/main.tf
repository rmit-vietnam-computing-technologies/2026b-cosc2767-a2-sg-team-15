# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Bao Nguyen Pham Gia
# ID: s4143691
# Created  date: 8/09/2026
# Last modified: 16/09/2026
# Acknowledgement: HashiCorp terraform documentation and documentation for AWS provider (see root main.tf)
# Not used due to Learner lab permissions

resource "aws_s3_bucket" "prod_bucket" {
  bucket = "rmitstore-prod-bucket"
  tags = {
    name = "FE production bucket"
  }
}

# Unblock public access

resource "aws_s3_bucket_public_access_block" "prod_public_unblock" {
  bucket = aws_s3_bucket.prod_bucket.id

  block_public_acls = false
  block_public_policy = false
  ignore_public_acls = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_acl" "prod_acl" {
  depends_on = [
    aws_s3_bucket_public_access_block.prod_public_unblock
  ]

  bucket = aws_s3_bucket.prod_bucket.id
  acl = "public-read"
}
