resource "aws_vpc" "main" {
  cidr_block = "10.0.67.0/24"
  enable_dns_support = true
  enable_dns_hostnames = true
  tags = {
    Name = "test-vpc"
  }
}

resource "aws_subnet" "public" {
  count = 1
  vpc_id = aws_vpc.main.id
  cidr_block = cidrsubnet(aws_vpc.main.cidr_block, 2, count.index)
  map_public_ip_on_launch = true
  tags = {
    Name = "pub-subnet1"
  }
}

resource "aws_subnet" "private" {
  count = 2
  vpc_id = aws_vpc.main.id
  cidr_block = cidrsubnet(aws_vpc.main.cidr_block, 2, count.index)
  tags {
    Name = "rds_"
  }
}
