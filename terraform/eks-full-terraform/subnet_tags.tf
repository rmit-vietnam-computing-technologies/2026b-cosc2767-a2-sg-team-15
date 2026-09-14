# The ALB controller looks for this tag to know which subnets it's allowed
# to place load balancers in. Since we're using the default VPC's existing
# subnets (not creating our own), we tag them in place rather than owning
# the subnet resources themselves.
resource "aws_ec2_tag" "public_subnet_elb" {
  for_each    = toset(data.aws_subnets.cluster_subnets.ids)
  resource_id = each.value
  key         = "kubernetes.io/role/elb"
  value       = "1"
}
