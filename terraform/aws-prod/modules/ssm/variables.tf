variable "environments" {
  description = "One media bucket per entry."
  type        = list(string)
  default     = ["staging", "prod"]
}

variable "db_username" {
  description = "Database username to set"
  type = string
}

variable "db_password" {
  description = "Database password to set"
  type = string
}

variable "rds_host" {
  type = string
}
