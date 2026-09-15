# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 15/09/2026
# Last modified: 15/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author applied and
#   verified it. Reference: Terraform output values,
#   https://developer.hashicorp.com/terraform/language/values/outputs

output "cluster_names" {
  description = "EKS name per tier, for update-kubeconfig and node group scaling."
  value       = { for k, c in aws_eks_cluster.this : k => c.name }
}

# Flat names too, since the root wires its kubernetes providers off these.
output "frontend_cluster_name" {
  description = "EKS name of the frontend cluster."
  value       = aws_eks_cluster.this["frontend"].name
}

output "frontend_cluster_endpoint" {
  description = "API endpoint of the frontend cluster."
  value       = aws_eks_cluster.this["frontend"].endpoint
}

output "frontend_cluster_ca" {
  description = "Base64 CA of the frontend cluster."
  value       = aws_eks_cluster.this["frontend"].certificate_authority[0].data
}

output "backend_cluster_name" {
  description = "EKS name of the backend cluster."
  value       = aws_eks_cluster.this["backend"].name
}

output "backend_cluster_endpoint" {
  description = "API endpoint of the backend cluster."
  value       = aws_eks_cluster.this["backend"].endpoint
}

output "backend_cluster_ca" {
  description = "Base64 CA of the backend cluster."
  value       = aws_eks_cluster.this["backend"].certificate_authority[0].data
}

output "cluster_endpoints" {
  description = "API endpoint per tier."
  value       = { for k, c in aws_eks_cluster.this : k => c.endpoint }
}

output "kubeconfig_commands" {
  description = "Writes a kubeconfig per tier that signs in with the current lab credentials."
  value = {
    for k, c in aws_eks_cluster.this :
    k => "aws eks update-kubeconfig --name ${c.name} --region us-east-1 --kubeconfig ${k}.kubeconfig"
  }
}

output "node_security_group_ids" {
  description = "Node SG per tier. Point the RDS ingress rule at the backend one."
  value       = { for k, sg in aws_security_group.nodes : k => sg.id }
}

output "node_group_names" {
  description = "Node group per tier, for scaling to 0 before End Lab."
  value       = { for k, ng in aws_eks_node_group.this : k => ng.node_group_name }
}
