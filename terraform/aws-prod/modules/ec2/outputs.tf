output "pub_sg_id" {
  description = "The ID of the Public Security Group"
  value = aws_security_group.public_sg.id
}

output "buildnode_sg_id" {
  description = "The ID of the buildnode security group"
  value = aws.security_group.jenkins_buildnode_sg.id
}

output "build_node_instance_id" {
  description = "The ID of the EC2 build node instance"
  value = aws_instance.public_main.id
}

output "jenkins_instance_id" {
  description = "the ID of the EC2 Jenkins Controller instance"
  value = aws_instance.public_jenkins.id
}

output "build_node_public_ip" {
  description = "The public IP of the build node instance"
  value = aws_instance.public_main.public_ip
}

output "jenkins_instance_public_ip" {
  description = "The public IP of the Jenkins instance"
  value = aws_instance.public_jenkins.public_ip
}
