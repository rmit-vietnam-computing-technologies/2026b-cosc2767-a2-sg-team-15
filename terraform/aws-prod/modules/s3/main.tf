resource "aws_s3_bucket" "prod_bucket" {
  bucket = "prod-bucket"
  tags = {
    name = "FE production bucket"
  }
}

resource "aws_s3_bucket" "canary_bucket" {
  bucket = "canary-bucket"
  tags = {
    name = "FE canary bucket"
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

  bucket = aws_s3_bucket.prod_bucket
  acl = "public-read"
}

resource "aws_s3_bucket_acl" "canary_acl" {
  depends_on = [
    aws_s3_bucket_public_access_block.prod_public_unblock
  ]

  bucket = aws_s3_bucket.canary_bucket
  acl = "public-read"
}
