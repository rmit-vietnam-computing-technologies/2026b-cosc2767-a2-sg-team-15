# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 13/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author applied and
#   verified it. Reference: Terraform variable definition files,
#   https://developer.hashicorp.com/terraform/language/values/variables#variable-definitions-tfvars-files

# TEMPLATE, placeholders only.  cp terraform.tfvars.example terraform.tfvars

# Bucket names are global. Change the suffix if apply says the name is taken.
bucket_suffix = "t15-260913"

# RDS master password. Letters and digits only, 8 to 41 chars, no @ / " or space.
db_password = "NIPshC6MXZzDUKkmWgEtXKXf"

# Learner Lab key pair. labsuser.pem is its private half.
keypair_name = "vockey"

# Your public IP as a /32 once you know it. Wide open is fine for a first apply.
admin_cidr = "0.0.0.0/0"

# Uncomment to build inside the team VPC from terraform/aws-individual.
# The first subnet listed hosts the node and must be public.
# vpc_id     = "vpc-REPLACE"
# subnet_ids = ["subnet-PUBLIC", "subnet-PRIVATE-A", "subnet-PRIVATE-B"]
create_eks = true
