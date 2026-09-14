# EKS + ALB + canary — full Terraform rebuild

This reproduces, from scratch, everything built manually: an EKS cluster on
a Learner Lab account, a frontend deployment with a canary variant, and an
ALB with weighted traffic splitting between them.

## Prerequisites before running this

1. **`devops_project_key` EC2 key pair must already exist** in the AWS console
   (EC2 > Key Pairs). Terraform references it but does not create it.
2. **Frontend images must already be pushed to ECR** before the Kubernetes
   resources can start successfully - Terraform creates the ECR repo, but
   does not build or push images. Push both a `:latest` and a `:canary`
   tagged image before running `terraform apply`, or the Deployments will
   sit in `ImagePullBackOff` until you do.
3. Update `frontend_image` / `frontend_canary_image` in `terraform.tfvars`
   if your account ID differs from the placeholder.

## Non-obvious things this file encodes, and why

**IMDS hop limit is set to 2 on the node launch template.**
Without this, the AWS Load Balancer Controller fails at startup trying to
reach instance metadata for credentials, with an error like
`no EC2 IMDS role found ... context deadline exceeded`. A pod's request to
IMDS counts as one extra network hop beyond the host, and the default hop
limit of 1 blocks it. This was discovered by trial and error - fixing it
here means nobody has to rediscover it.

**No IRSA / OIDC provider.**
Normally the ALB Controller gets its own dedicated IAM role via IRSA. A
Learner Lab account can't create new IAM roles, so instead the controller
borrows the node's own `LabRole` permissions via IMDS (see above). This is
not how you'd do it in a real production AWS account - it's a deliberate
shortcut for this constraint.

**Worker node security group opens ports 30000-32767, 80, 22, and 10250.**
Each of these was a real failure encountered manually:
- 30000-32767 (NodePort range): without it, `LoadBalancer`/`NodePort`
  services show target health as `OutOfService`.
- 80: the ALB (in `target-type: ip` mode) talks directly to pod IPs on
  this port, which live on the node's network interface.
- 22: needed for SSH-based troubleshooting.
- 10250: control plane to kubelet. Note this fixes a *different* problem
  than the two above - `kubectl logs`/`exec` can still fail with a
  `tls: internal error` even with this open, which is a kubelet TLS
  handshake incompatibility, not a security group block.

**Subnets are tagged, not owned.**
This uses the account's default VPC rather than creating a new one, so
subnets are tagged in place via `aws_ec2_tag` (which can tag existing
resources without owning them) rather than via `tags` on an
`aws_subnet` resource Terraform would need to create.

**Ingress uses a "virtual" weighted backend.**
`frontend-weighted` in `k8s_ingress.tf` is not a real Kubernetes Service -
it only exists as the annotation key
`alb.ingress.kubernetes.io/actions.frontend-weighted`. The `use-annotation`
port name is a magic value the ALB Controller recognizes as "use that
annotation's weighted forward config instead of a real service port."
This is the standard (if unusual-looking) pattern for canary/weighted
routing with this controller.

## Running it

```bash
terraform init
terraform plan
terraform apply
```

Cluster + node group provisioning takes ~15-20 minutes. Once complete:

```bash
kubectl get ingress frontend-ingress
```

Watch the `ADDRESS` column for the ALB's DNS name to appear (can take a
couple of minutes after apply finishes, since the controller reconciles
asynchronously).

## Known gaps / things left manual

- `kubectl logs` / `kubectl exec` may still fail with a kubelet TLS error
  unrelated to anything in this Terraform - use
  `sudo crictl exec -it <container-id> sh` directly on the node instead
  if you hit this.
- TLS (ACM certificate) and DNS are not included here - add the
  `alb.ingress.kubernetes.io/certificate-arn` and related annotations to
  `k8s_ingress.tf` once a certificate is issued.
- Backend deployment is not included yet - follow the same pattern as
  `k8s_frontend.tf` for a second Deployment/Service pair, then add a path
  rule (e.g. `/api`) to `k8s_ingress.tf` alongside the weighted `/` rule.
