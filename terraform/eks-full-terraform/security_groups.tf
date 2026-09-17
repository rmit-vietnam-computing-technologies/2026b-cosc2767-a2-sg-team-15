# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Nguyen Bao Toan
# ID: s3926310
# Created  date: 05/09/2026
# Last modified: 17/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it again. References: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_cluster

# Security group for the EKS cluster control plane
resource "aws_security_group" "eks_cluster_sg" {
  name        = "${var.cluster_name}-sg"
  description = "Security group for ${var.cluster_name} EKS cluster"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Allow all internal traffic within the security group"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.cluster_name}-sg"
  }
}

# Security group attached to worker nodes.
# Every rule here was something we discovered was missing through hands-on
# debugging - documented so nobody has to rediscover it:
#   - NodePort range: needed for the ELB (or ALB's target-type instance mode)
#     to reach services of type LoadBalancer / NodePort
#   - Port 80: needed for the ALB (target-type ip) to reach pods directly
#   - Port 22: needed for SSH troubleshooting (kubectl logs/exec is broken
#     by a separate kubelet TLS issue unrelated to security groups)
#   - Port 10250: control plane -> kubelet, needed for some cluster
#     management operations
resource "aws_security_group" "node_sg" {
  name        = "${var.cluster_name}-node-sg"
  description = "Security group for ${var.cluster_name} worker nodes"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "NodePort range - needed for LoadBalancer/NodePort services"
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Direct pod access for ALB target-type ip"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH for troubleshooting"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Control plane to kubelet"
    from_port   = 10250
    to_port     = 10250
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow all internal node-to-node traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.cluster_name}-node-sg"
    # Required for kubernetes.io/cluster tagging conventions
    "kubernetes.io/cluster/${var.cluster_name}" = "owned"
  }
}

resource "aws_security_group" "eksctl_server_sg" {
  name        = "eksctl_kubectl_server_security_group"
  description = "Allow SSH only"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH from anywhere (lab setting only)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "eksctl_kubectl_server_security_group"
  }
}
