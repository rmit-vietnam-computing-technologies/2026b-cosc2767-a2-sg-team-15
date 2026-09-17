# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Bao Nguyen Pham Gia
# ID: s4143691
# Created  date: 8/09/2026
# Last modified: 16/09/2026
# Acknowledgement: HashiCorp terraform documentation and documentation for AWS provider (see root main.tf)

output "jenkins_sg_id" {
  description = "The ID of the jenkins Security Group"
  value = aws_security_group.jenkins_sg.id
}

output "buildnode_sg_id" {
  description = "The ID of the buildnode security group"
  value = aws_security_group.jenkins_buildnode_sg.id
}

output "build_node_instance_id" {
  description = "The ID of the EC2 build node instance"
  value = aws_instance.lim_public_jenkins_buildnode.id
}

output "jenkins_instance_id" {
  description = "the ID of the EC2 Jenkins Controller instance"
  value = aws_instance.public_jenkins.id
}

output "build_node_public_ip" {
  description = "The public IP of the build node instance"
  value = aws_instance.lim_public_jenkins_buildnode.public_ip
}

output "jenkins_instance_public_ip" {
  description = "The public IP of the Jenkins instance"
  value = aws_eip.jenkins_eip.public_ip
}

output "prometheus_instance_id" {
  description = "the ID of the EC2 prometheus instance"
  value = aws_instance.public_prometheus.id
}

output "prometheus_public_ip" {
  description = "The public IP of the prometheus instance"
  value = aws_eip.prometheus_eip.public_ip
}
