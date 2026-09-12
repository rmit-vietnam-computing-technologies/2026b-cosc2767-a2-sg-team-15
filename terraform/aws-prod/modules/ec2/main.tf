data "aws_ami" "debian" {
  most_recent = true
  filter {
    name = "name"
    values = ["debian-13-amd64-*"]
  }
  filter {
    name = "virtualization-type"
    values = ["hvm"]
  }

    owners = ["136693071363"]
}

# Import the LabInstanceProfile
import {
  identity = {
    name = "LabInstanceProfile"
  }
  to = aws_iam_instance_profile.LabInstanceProfile
}

resource "aws_iam_instance_profile" "LabInstanceProfile" {
  # Left blank beacuse it's already imported
}

resource "aws_security_group" "jenkins_sg" {
  name = "jenkins-sg"
  description = "Allow web and SSH traffic"
  vpc_id = var.vpc_id

  ingress {
    description = "SSH"
    from_port = 22
    to_port = 22
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP"
    from_port = 80
    to_port = 80
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "jenkins_buildnode_sg" {
  name = "jenkins-buildnode-sg"
  description = "Allow SSH traffic for build node config"
  vpc_id = var.vpc_id
  # Only allow outbound internet access for downloading packages
  # And ssh for initial Ansible setup
  ingress {
    description = "SSH"
    from_port = 22
    to_port = 22
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    # Also explicitly allow SSH from the jenkins ctr node
    security_groups = [aws_security_group.jenkins_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}


resource "aws_instance" "public_jenkins" {
  ami = data.aws_ami.debian.id
  instance_type = "t3.micro"
  key_name = var.keypair_name
  subnet_id = var.vpc_public_subnet_id
  vpc_security_group_ids = [aws_security_group.jenkins_sg.id]
  iam_instance_profile = aws_iam_instance_profile.LabInstanceProfile.name
  tags = {
    Name = "jenkins instance"
  }
}

resource "aws_instance" "public_prometheus" {
  ami = data.aws_ami.debian.id
  instance_type = "t3.micro"
  key_name = var.keypair_name
  subnet_id = var.vpc_public_subnet_id
  vpc_security_group_ids = [aws_security_group.jenkins_sg.id]
  iam_instance_profile = aws_iam_instance_profile.LabInstanceProfile.name
  tags = {
    Name = "prometheus instance"
  }
}

resource "aws_instance" "lim_public_jenkins_buildnode" {
  ami = data.aws_ami.debian.id
  instance_type = "t3.micro"
  key_name = var.keypair_name
  subnet_id = var.vpc_public_subnet_id
  vpc_security_group_ids = [aws_security_group.jenkins_buildnode_sg.id]
  iam_instance_profile = aws_iam_instance_profile.LabInstanceProfile.name
  tags = {
    Name = "jenkins build node instance"
  }
}

resource "aws_eip" "jenkins_eip" {
  instance = aws_instance.public_jenkins.id
  domain = "vpc"
}

resource "aws_eip" "prometheus_eip" {
  instance = aws_instance.public_prometheus.id
  domain = "vpc"
}
