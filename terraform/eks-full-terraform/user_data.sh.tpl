#!/bin/bash
set -e

hostnamectl set-hostname eksctl-kubectl-server

# --- kubectl ---
curl -O https://s3.us-west-2.amazonaws.com/amazon-eks/${cluster_version}.0/2024-01-04/bin/linux/amd64/kubectl
chmod +x ./kubectl
mkdir -p /root/bin
mv ./kubectl /root/bin/kubectl
echo 'export PATH=$PATH:$HOME/bin' >> /root/.bashrc

# --- eksctl ---
curl --silent --location "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz" | tar xz -C /tmp
mv /tmp/eksctl /usr/local/bin

# --- Docker (needed to build/push images to ECR - not in the original tutorial) ---
yum install docker -y
systemctl enable --now docker
usermod -aG docker ec2-user

# --- Helm (needed for the AWS Load Balancer Controller) ---
curl -fsSL -o /tmp/helm.tar.gz https://get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz
tar -zxvf /tmp/helm.tar.gz -C /tmp
mv /tmp/linux-amd64/helm /usr/local/bin/helm

# --- kubeconfig ---
export PATH=$PATH:/root/bin
aws eks update-kubeconfig --region ${aws_region} --name ${cluster_name}
chmod 600 /root/.kube/config
