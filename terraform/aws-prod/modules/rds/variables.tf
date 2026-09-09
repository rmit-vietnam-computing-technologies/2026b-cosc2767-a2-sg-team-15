variable "subnet_ids" {
  description = "The subnet ids for the RDS database"
  type = list(string)
}

variable "rds_username" {
  description = "RDS username"
  type = string
}

variable "rds_password" {
  description = "RDS password"
  type = string
}
