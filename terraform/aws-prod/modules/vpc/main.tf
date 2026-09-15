data "aws_ec2_instance_type_offerings" "t3micro_available" {
  filter {
    name = "instance-type"
    values = ["t3.micro"]
  }
  location_type = "availability-zone"
}

# The offerings list comes back in a different order on every plan, and an
# AZ change on a subnet is a replace. Sort it and take the first two, which
# also keeps us-east-1e out: EKS control planes cannot use it.
locals {
  azs = slice(sort([for az in data.aws_ec2_instance_type_offerings.t3micro_available.locations : az if az != "us-east-1e"]), 0, 2)
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.67.0/24"
  enable_dns_support = true
  enable_dns_hostnames = true
  tags = {
    Name = "prod-vpc"
  }
}

resource "aws_subnet" "public" {
  count = 2
  vpc_id = aws_vpc.main.id
  availability_zone = local.azs[count.index]
  cidr_block = cidrsubnet(aws_vpc.main.cidr_block, 2, count.index)
  map_public_ip_on_launch = true
  tags = {
    Name = "pub-subnet${count.index}"
  }
}



resource "aws_subnet" "private" {
  count = 2
  vpc_id = aws_vpc.main.id
  availability_zone = local.azs[count.index]
  cidr_block = cidrsubnet(aws_vpc.main.cidr_block, 2, count.index+2)
  tags = {
    Name = "priv-subnet${count.index}"
  }
}

resource "aws_internet_gateway" "igw1" {
  vpc_id = aws_vpc.main.id
  tags = {
    Name = "igw1"
  }
}

resource "aws_route_table" "inet_rt" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw1.id
  }

  tags = {
    Name = "inet_rt"
  }
}

resource "aws_route_table_association" "inet_assoc" {
  count = 2
  subnet_id = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.inet_rt.id
}
