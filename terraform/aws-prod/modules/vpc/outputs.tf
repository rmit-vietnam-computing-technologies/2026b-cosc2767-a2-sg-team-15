output "vpc_id" {
  description = "The ID of the VPC"
  value = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "The ID of the public subnet"
  value = aws_subnet.public[0].id
}

output "private_subnet_ids" {
  description = "The IDs of the private subnets"
  value = aws_subnet.private[*].id
}

output "igw_id" {
  description = "The ID of the Internet Gateway"
  value = aws_internet_gateway.igw1.id
}
