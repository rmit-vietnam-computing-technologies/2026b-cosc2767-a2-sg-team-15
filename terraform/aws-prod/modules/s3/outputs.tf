output "prod_bucket_name" {
  description = "Name of the production bucket"
  value = aws_s3_bucket.prod_bucket.bucket
}
