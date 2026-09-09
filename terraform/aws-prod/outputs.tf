output "buildnode_instance_public_ip" {
  description = "The public IP of the build node instance"
  value = module.ec2.build_node_public_ip
}

output "jenkins_instance_public_ip" {
  description = "The public IP of the Jenkins instance"
  value = module.ec2.jenkins_instance_public_ip
}
