## Production Terraform Setup

Most of the things you see began as a copy of the individual AWS terraform, now modified with more stuff for production.

### Provisioned infra

- [x] One VPC (`10.0.67.0/24`) subdivided into 2 public and 2 private subnets
- [x] Three EC2 instances, 2 of them for Jenkins (1 controller, 1 agent), one for prometheus
- [ ] 2 EKS clusters, one for Production, one for Canary
- [x] 1 AWS RDS PostgreSQL instance
- [ ] 2 Application Load Balancers (ALB) for Frontend and Backend EKS
- [x] TLS certificates from Amazon for the FE and API load balancers
- [x] Cloudflare DNS records, because the author of this whole thing owns a domain <(")

### How to use

- Refer to the readme in `terraform/aws-indvidual` and fill in additional variables
- You **must** use terraform, not opentofu, because there are some things that require it, mainly:
  - Importing `LabInstanceProfile` into terraform, and
  - `ansible_playbook_run`, so the ansible playbook will autorun once EC2 provisioning is complete
- The Jenkins controller instance and prometheus will have its traffic secured using Letsencrypt HTTPS certificates.
  
### Known issues

- Not using AWS Route53 for DNS because learner lab doesn't support using Route53.
- S3 module is included but not enabled
  - AWS Learner Lab does not allow any kind of object lock config access
  - Terraform will try to read object lock config and will fail, even though the bucket is created
  - Post-actions, such as unblocking public access, will not be performed
