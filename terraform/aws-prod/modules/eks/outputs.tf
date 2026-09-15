output "frontend_cluster_name" {
  value = aws_eks_cluster.frontend_cluster.name
}
output "frontend_cluster_endpoint" {
  value = aws_eks_cluster.frontend_cluster.endpoint
}
output "frontend_cluster_ca" {
  value = aws_eks_cluster.frontend_cluster.certificate_authority[0].data
}

output "backend_cluster_name" {
  value = aws_eks_cluster.backend_cluster.name
}
output "backend_cluster_endpoint" {
  value = aws_eks_cluster.backend_cluster.endpoint
}
output "backend_cluster_ca" {
  value = aws_eks_cluster.backend_cluster.certificate_authority[0].data
}
