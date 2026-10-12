# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Nguyen Bao Toan
# ID: s3926310
# Created  date: 05/09/2026
# Last modified: 17/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it again. References: https://developer.hashicorp.com/terraform/tutorials/aws-get-started/aws-create

aws_region            = "us-east-1"
cluster_name          = "devops-eks-cluster"
cluster_version       = "1.30"
availability_zones    = ["us-east-1a", "us-east-1b", "us-east-1c"]
node_group_name       = "devops-workers-group"
node_instance_types   = ["t3.medium"]
node_disk_size        = 20
node_desired_size     = 2
node_min_size         = 2
node_max_size         = 2
key_pair_name         = "devops_project_key"
eksctl_instance_name  = "eksctl_kubectl_server"
eksctl_instance_type  = "t3.micro"
ecr_repository_name   = "webapp-frontend-terraform"

# Replace with your actual account ID if different
frontend_image         = "592505311891.dkr.ecr.us-east-1.amazonaws.com/webapp-frontend:latest"
frontend_canary_image  = "592505311891.dkr.ecr.us-east-1.amazonaws.com/webapp-frontend:canary"
frontend_container_port = 80
frontend_replicas      = 3
canary_replicas        = 1
canary_weight          = 10
