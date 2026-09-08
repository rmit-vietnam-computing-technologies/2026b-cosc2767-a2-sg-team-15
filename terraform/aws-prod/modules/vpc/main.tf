data "aws_ec2_instance_type_offerings" "t3micro_available" {
  filter {
    name = "instance-type"
    values = ["t3.micro"]
  }
  location_type = "availability-zone"
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
  availability_zone = data.aws_ec2_instance_type_offerings.t3micro_available.locations[count.index]
  cidr_block = cidrsubnet(aws_vpc.main.cidr_block, 2, count.index)
  map_public_ip_on_launch = true
  tags = {
    Name = "pub-subnet${count.index}"
  }
}



resource "aws_subnet" "private" {
  count = 2
  vpc_id = aws_vpc.main.id
  availability_zone = data.aws_ec2_instance_type_offerings.t3micro_available.locations[count.index]
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
  count = 1
  subnet_id = aws_subnet.public[0].id
  route_table_id = aws_route_table.inet_rt.id
}
