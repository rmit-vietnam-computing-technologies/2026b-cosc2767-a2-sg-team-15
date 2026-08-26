output "pub_sg_id" {
  description = "The ID of the Public Security Group"
  value = aws_security_group.public_sg.id
}

output "main_instance_id" {
  description = "The ID of the EC2 NAT/nginx instance"
  value = aws_instance.public_main.id
}

output "jenkins_instance_id" {
  description = "the ID of the EC2 Jenkins Controller instance"
  value = aws_instance.public_jenkins.id
}

output "main_instance_public_ip" {
  description = "The public IP of the NAT/nginx instance"
  value = aws_instance.public_main.public_ip
}

output "jenkins_instance_public_up" {
  description = "The public IP of the Jenkins instance"
  value = aws_instance.public_jenkins.public_ip
}
