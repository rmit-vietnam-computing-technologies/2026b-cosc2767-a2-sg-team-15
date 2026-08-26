variable "keypair_name" {
  description = "The name of the Keypair that will be applied to **EVERY** ec2 instance"
  type = string
}

variable "vpc_public_subnet_id" {
  description = "The subnetID of the VPC where the EC2 instance will be located"
  type = string
}

variable "vpc_private_subnet_id" {
  description = "The SubnetID of the private VPC where the EC2 instance will be located"
  type = string
}

variable "vpc_id" {
  description = "The ID of the VPC"
  type = string
}
