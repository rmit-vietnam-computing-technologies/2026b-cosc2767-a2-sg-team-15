<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 14/09/2026
Last modified: 14/09/2026
Acknowledgement: Written with help from Claude (Anthropic). Every command
  here was run by the author in this order on a Learner Lab account.
-->

# Backend pipeline: how to run it on a clean AWS account

The API tier as a container image, on Kubernetes in two namespaces, with RDS
for the database and S3 for uploads. The cluster is k3s on one node by
default, or EKS behind a Terraform flag; the manifests and scripts are the
same on both. Everything below is in this repo; nothing is clicked in the
console.

## Layout

| Path | What |
|---|---|
| `terraform/backend/` | Node, RDS, media buckets, the app secrets in SSM Parameter Store, and the optional EKS cluster (`eks.tf`) |
| `deploy/ansible/` | Turns the node into a k3s cluster, creates the per-environment databases |
| `deploy/k8s/` | Kubernetes manifests (kustomize base, `staging` and `prod` overlays, one-shot jobs) and per-environment config |
| `deploy/bin/` | The six scripts Jenkins calls: `test`, `build-push`, `deploy`, `seed`, `smoke`, `rollback` |
| `deploy/jenkins/api-stages.groovy` | The stages to paste into `webapp/Jenkinsfile` |
| `webapp/server/Dockerfile`, `webapp/server/docker/` | The API image: nginx on 80 in front of gunicorn |
| `webapp/server/tests/` | 12 tests: unit, integration, smoke |
| `compose.yaml`, `compose.ci.yaml` | Local stack and the CI test run |

## Prerequisites on the machine running this

Terraform >= 1.6, Ansible, kubectl, Docker, AWS CLI, and a Learner Lab
session with its CLI credentials in `~/.aws/credentials` and its key pair as
`~/.ssh/labsuser.pem`.

## 1. Infrastructure

```bash
cd terraform/backend
cp terraform.tfvars.example terraform.tfvars      # set bucket_suffix and db_password
terraform init
terraform apply                                    # about 8 minutes, RDS is the slow part
terraform output                                   # node IP, RDS endpoint, buckets, SSM paths
```

Creates: one `t3.medium` with an Elastic IP and the `LabInstanceProfile`,
one `db.t3.micro` Postgres 16 reachable only from the node, two media buckets
with public read on `media/*`, and eight SSM parameters under
`/rmit-store/staging/` and `/rmit-store/prod/` (Django secret, database
URL, seed admin login). The buckets are created through the CLI from inside
Terraform because the Learner Lab denies an S3 read the provider insists on.

## 2. Cluster

### 2a. k3s on the node (default)

```bash
cd ../../deploy/ansible
cp inventory.ini.example inventory.ini             # node IP
cp group_vars/all.yml.example group_vars/all.yml   # node IP, RDS endpoint, db password
ansible-galaxy collection install -r requirements.yml
ansible-playbook site.yml                          # k3s, then rmit_staging and rmit_prod on RDS
export KUBECONFIG=$PWD/k3s.kubeconfig
kubectl get nodes                                  # Ready
```

### 2b. EKS

Needs 2a to have run once, for the databases on RDS. Then:

```bash
cd terraform/backend
echo 'create_eks = true' >> terraform.tfvars
terraform apply                                    # control plane about 11 minutes, node group about 2
cd ../..
$(cd terraform/backend && terraform output -raw eks_kubeconfig_command)
export KUBECONFIG=$PWD/deploy/ansible/eks.kubeconfig
kubectl get nodes                                  # two Ready
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml   # the HPA needs it; k3s bundles it
```

Creates: the cluster on `LabRole` (the lab cannot create the roles EKS
would normally get), an access entry that makes the lab session role
cluster admin, a `t3.small` node group of two in `us-east-1a` and `1b`, a
node security group that the RDS group admits, and the subnet tags the
load balancer controller looks for. `type: LoadBalancer` becomes one classic
ELB per namespace; `deploy.sh` waits for it and prints its address.

`terraform apply -var create_eks=false` removes all of it, after the
namespaces are gone (see the end of this file).

## 3. Environment config

`deploy/k8s/staging.config.env` and `prod.config.env` hold the public
settings (allowed hosts, bucket, smoke URL). Put the node IP and bucket
names from `terraform output` in both. The ELB domain is already allowed,
so EKS needs nothing extra here. Secrets are never in a file: `deploy.sh`
reads them from SSM at deploy time.

## 4. Deploy by hand

```bash
cd ../..
export ECR_REPO=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/rmit-store-api   # repo is created on first push
export KUBECONFIG=$PWD/deploy/ansible/k3s.kubeconfig     # or eks.kubeconfig
TAG=$(git rev-parse --short HEAD)

deploy/bin/test.sh $TAG               # suite against a throwaway Postgres, reports in webapp/server/test-reports/
deploy/bin/build-push.sh $TAG         # runtime image, tagged with the commit, pushed to ECR
deploy/bin/deploy.sh staging $TAG     # secrets from SSM, migrate once, roll two replicas, wait
deploy/bin/seed.sh staging $TAG       # demo catalogue and accounts, first time only
deploy/bin/smoke.sh staging $TAG      # probes, version equals $TAG, declined-card check
deploy/bin/deploy.sh prod $TAG        # same image, promoted
deploy/bin/seed.sh prod $TAG
deploy/bin/smoke.sh prod $TAG
```

On k3s staging answers on `http://<node-ip>:8080` and prod on
`http://<node-ip>`; on EKS each namespace has its own ELB hostname, printed
by `deploy.sh` and read back by `smoke.sh` and `rollback.sh` from the
Service. `/api/version/` reports the commit that is serving.

## 5. Jenkins

Credentials, by ID: `aws-access-key-id`, `aws-secret-access-key`,
`aws-session-token` (strings, from the Learner Lab, re-entered each session)
and `k3s-kubeconfig` (secret file, `deploy/ansible/k3s.kubeconfig`). The
stages in `deploy/jenkins/api-stages.groovy` run the same six scripts:
test, build and push, deploy staging, smoke staging, and on `main` only,
deploy prod and smoke prod. A red stage stops the run before prod and mails
the team. Push to the repo to trigger it.

## 6. Roll back

```bash
deploy/bin/rollback.sh prod           # kubectl rollout undo, then polls /api/version/ until the previous commit answers
```

Migrations are additive and are not rolled back; the code is what moves.
A migration that fails stops the deploy before any pod changes.

## 7. Scale

```bash
kubectl -n prod get hpa               # 2 to 4 replicas on 70% CPU
kubectl -n prod scale deployment/api --replicas=3
```

Uploads go to S3, so any number of replicas share one media store.

## Adding an environment

Say `dev`, alongside `staging` and `prod`:

1. `terraform/backend/terraform.tfvars`: `environments = ["staging", "prod", "dev"]`, then `terraform apply` (adds the bucket and the four SSM parameters).
2. `deploy/ansible/group_vars/all.yml`: add `rmit_dev` to `db_names`, then `ansible-playbook site.yml --tags database`.
3. `deploy/k8s/overlays/dev/kustomization.yaml`: copy the staging one, set `namespace: dev` and a free port (say 8081); on k3s also open that port in the node security group (`terraform/backend/main.tf`). On EKS the new ELB brings its own.
4. `deploy/k8s/dev.config.env`: copy the staging one, change the port and the bucket name.
5. `deploy/bin/deploy.sh dev <tag>`, `seed.sh dev <tag>`, `smoke.sh dev <tag>`.

To bypass SSM for a one-off (no AWS access on the machine, say), copy
`deploy/k8s/<env>.secret.env.example` to `<env>.secret.env`, fill it, and run
with `SECRET_FILE=deploy/k8s/<env>.secret.env`.

## When the Learner Lab session ends

Credentials stop working and the node is stopped. Start the lab, refresh
`~/.aws/credentials`, then:

```bash
aws ec2 start-instances --instance-ids <node-instance-id>
```

Elastic IP, private IP, RDS, buckets and the k3s service come back as they were.

EKS nodes live in an Auto Scaling group, which does not take kindly to
being stopped from outside. Scale the group to zero before ending the lab
and back afterwards; the control plane, addresses and namespaces persist,
and pods reschedule as soon as a node is back.

```bash
aws eks update-nodegroup-config --cluster-name rmit-store-eks --nodegroup-name rmit-store-eks-nodes --scaling-config minSize=0,maxSize=3,desiredSize=0   # before End Lab
aws eks update-nodegroup-config --cluster-name rmit-store-eks --nodegroup-name rmit-store-eks-nodes --scaling-config minSize=2,maxSize=3,desiredSize=2   # after Start Lab
```

Terraform ignores `desired_size`, so neither command shows up as drift.

## Removing EKS

The ELBs belong to the Services, not to Terraform, and their security
groups block the cluster's from being deleted. Namespaces first:

```bash
KUBECONFIG=deploy/ansible/eks.kubeconfig kubectl delete ns staging prod
cd terraform/backend && terraform apply -var create_eks=false
```

