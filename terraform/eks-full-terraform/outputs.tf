output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_status" {
  value = aws_eks_cluster.this.status
}

output "node_group_status" {
  value = aws_eks_node_group.devops_workers.status
}

output "ecr_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "eksctl_server_public_ip" {
  value = aws_instance.eksctl_kubectl_server.public_ip
}

output "configure_kubectl_locally" {
  value = "aws eks update-kubeconfig --region ${var.aws_region} --name ${aws_eks_cluster.this.name}"
}

output "alb_ingress_note" {
  value = "Run `kubectl get ingress frontend-ingress` after apply completes - the ALB's DNS name appears in the ADDRESS column within a couple of minutes."
}
