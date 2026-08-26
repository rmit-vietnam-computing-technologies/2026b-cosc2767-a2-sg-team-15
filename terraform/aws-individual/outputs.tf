output "main_instance_public_ip" {
  description = "The public IP of the NAT/nginx instance"
  value = module.ec2.main_instance_public_ip
}

output "jenkins_instance_public_ip" {
  description = "The public IP of the Jenkins instance"
  value = module.ec2.jenkins_instance_public_ip
}
