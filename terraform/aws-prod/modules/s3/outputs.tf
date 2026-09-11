output "prod_bucket_name" {
  description = "Name of the production bucket"
  value = aws_s3_bucket.prod_bucket.bucket
}

output "canary_bucket_name" {
  description = "Name of the canary bucket"
  value = aws_s3_bucket.canary_bucket.bucket
}
