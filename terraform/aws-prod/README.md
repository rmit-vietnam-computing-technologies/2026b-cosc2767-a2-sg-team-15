## Production Terraform Setup

Most of the things you see began as a copy of the individual AWS terraform, now modified with more stuff for production.

### Provisioned infra

- [x] One VPC (`10.0.67.0/24`) subdivided into 2 public and 2 private subnets
- [x] Two EC2 instances, all of them for Jenkins (1 controller, 1 agent)
- [ ] 2 sets of EKS clusters, including one cluster for Frontend, one for Backend, 1 set for production, 1 set for Canary
- [ ] 2 AWS RDS PostgreSQL instances, one for production, one for Canary
- [ ] Application Load Balancers (ALB) for Frontend and Backend EKS (4 in total)
- [x] TLS certificates from Amazon for the FE load balancers
- [x] Cloudflare DNS records, because the author of this whole thing owns a domain <(")

### How to use

- Refer to the readme in `terraform/aws-indvidual` and fill in additional variables
- Not using AWS Route53 for DNS because learner lab doesn't support using Route53.
- The Jenkins controller instance will have its traffic secured using Letsencrypt HTTPS certificates.
