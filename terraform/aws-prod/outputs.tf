// RMIT University Vietnam
// Course: COSC2767|COSC2805 Systems Deployment and Operations
// Semester: 2026B
// Assessment: Assignment 2
// Author: Bao Nguyen Pham Gia
// ID: s4143691
// Created  date: 8/09/2026
// Last modified: 16/09/2026
// Acknowledgement: HashiCorp terraform documentation

output "buildnode_instance_public_ip" {
  description = "The public IP of the build node instance"
  value = module.ec2.build_node_public_ip
}
