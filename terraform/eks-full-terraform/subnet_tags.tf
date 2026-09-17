# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Nguyen Bao Toan
# ID: s3926310
# Created  date: 05/09/2026
# Last modified: 17/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it again. References: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/elb

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
