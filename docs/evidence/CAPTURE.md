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
  was run by the author on the live environment.
-->

# Capturing the backend evidence

One screenshot per point, named as in `README.md`. Run from the repo root
with a live lab session. Setup once per terminal:

```bash
export KUBECONFIG=$PWD/deploy/ansible/k3s.kubeconfig     # eks.kubeconfig for the EKS set
export ECR_REPO=115972158049.dkr.ecr.us-east-1.amazonaws.com/rmit-store-api
TAG=$(git rev-parse --short HEAD)
NODE=54.144.69.199
```

Frame each capture so the command and its output are both visible. Crop
the docker build noise; the last lines are what matter.

## Infrastructure

**terraform-backend-apply.png**: converged state and outputs.

```bash
cd terraform/backend && terraform plan -no-color | tail -3 && terraform state list && terraform output; cd ../..
```

**k3s-node-ready-via-ansible.png**: idempotent playbook and a Ready node.

```bash
cd deploy/ansible && ansible-playbook site.yml | tail -6 && kubectl get nodes -o wide; cd ../..
```

## Image and tests

**api-image-nginx-probes.png**: probes with a pod-IP Host pass, real requests still need `ALLOWED_HOSTS`, every process is `app`, the container dies with gunicorn.

```bash
docker run -d --name api-probe -p 8000:80 -e SECRET_KEY=verify-only -e ALLOWED_HOSTS=localhost,127.0.0.1 \
  -e DATABASE_URL=postgres://x:x@127.0.0.1:1/x rmit-store-api:$TAG && sleep 3
curl -s -o /dev/null -w '%{http_code} healthz\n'                http://localhost:8000/healthz/
curl -s -o /dev/null -w '%{http_code} readyz (db down)\n'       http://localhost:8000/readyz/
curl -s -o /dev/null -w '%{http_code} static via nginx\n'       http://localhost:8000/static/admin/css/base.css
curl -s -o /dev/null -w '%{http_code} probe with pod-ip Host\n' -H 'Host: 10.42.0.7' http://localhost:8000/healthz/
curl -s -o /dev/null -w '%{http_code} api with pod-ip Host\n'   -H 'Host: 10.42.0.7' http://localhost:8000/api/version/
docker exec api-probe bash -c 'for p in $(ls /proc | grep -E "^[0-9]+$" | sort -n); do printf "%-5s %-5s %s\n" "$p" "$(stat -c %U /proc/$p)" "$(tr "\0" " " < /proc/$p/cmdline)"; done' 2>/dev/null | grep -v '^[0-9]*  *$'
docker exec api-probe bash -c 'for p in $(ls /proc | grep -E "^[0-9]+$" | sort -n); do grep -qa gunicorn /proc/$p/cmdline && { kill -TERM $p; break; }; done'
sleep 3; docker inspect -f '{{.State.Status}} exit={{.State.ExitCode}}' api-probe; docker rm -f api-probe
```

**compose-stack-nginx-api.png**: the local stack through port 80.

```bash
docker compose up -d --build >/dev/null && docker compose ps && curl -s localhost/api/version/; echo; docker compose down
```

**tests-twelve-green.png**: the suite inside the image against real Postgres.

```bash
deploy/bin/test.sh $TAG 2>&1 | tail -40
```

**tests-smoke-in-stack.png**: smoke from inside the Compose network.

```bash
docker compose up -d && docker compose --profile seed run --rm seed >/dev/null
docker compose -f compose.yaml -f compose.ci.yaml run --rm -e SMOKE_BASE_URL=http://web -e SMOKE_EXPECTED_COMMIT=$TAG \
  -e SMOKE_MEMBER_EMAIL=$(grep ^SEED_ADMIN_EMAIL .env | cut -d= -f2) -e SMOKE_MEMBER_PASSWORD=$(grep ^SEED_ADMIN_PASSWORD .env | cut -d= -f2) \
  test pytest -m smoke --no-cov
docker compose down
```

## Kubernetes

**k3s-staging-two-replicas-s3.png**: two replicas, LoadBalancer, HPA, storage ok, media on the bucket.

```bash
kubectl -n staging get pods,svc,hpa
curl -s http://$NODE:8080/readyz/; echo
curl -s http://$NODE:8080/api/products/ | grep -o '"image_url":"[^"]*"' | head -1
```

**k3s-staging-and-prod-two-namespaces.png**: same image, two environments.

```bash
kubectl get pods -n staging | grep api; kubectl get pods -n prod | grep api
kubectl get svc -A | grep LoadBalancer
for p in 8080 80; do curl -s http://$NODE:$p/api/version/; echo; done
```

**k3s-rollback-version-check.png**: back one revision, verified from outside, then forward again.

```bash
deploy/bin/rollback.sh staging
kubectl -n staging rollout history deployment/api
deploy/bin/deploy.sh staging $TAG >/dev/null && curl -s http://$NODE:8080/api/version/; echo
```

**k3s-hpa-scale.png**: scaling by hand and the HPA bounds.

```bash
kubectl -n prod scale deployment/api --replicas=3 && sleep 20 && kubectl -n prod get pods,hpa
kubectl -n prod scale deployment/api --replicas=2
```

**secrets-from-ssm.png**: the Secret holds the SSM value.

```bash
[ "$(kubectl -n staging get secret api-secret -o jsonpath='{.data.SEED_ADMIN_PASSWORD}' | base64 -d)" = \
  "$(aws ssm get-parameter --name /rmit-store/staging/SEED_ADMIN_PASSWORD --with-decryption --query Parameter.Value --output text)" ] && echo "secret matches SSM"
cd terraform/backend && terraform output ssm_parameter_paths; cd ../..
```

**metrics-endpoint-through-nginx.png**: metrics served through the container's nginx, Host header handled.

```bash
curl -s http://$NODE/metrics | grep -E '^django_http_(responses_total_by_status_total|requests_latency_seconds_by_view_method_count)' | head -4
curl -s -o /dev/null -w '%{http_code}\n' -H "Host: 172.31.81.134:80" http://$NODE/metrics
```

## EKS

Same manifests, same scripts, second cluster. `KUBECONFIG` points at
`deploy/ansible/eks.kubeconfig` for all of these; the ELB hostnames come
from the Services.

```bash
export KUBECONFIG=$PWD/deploy/ansible/eks.kubeconfig
STAGING=$(kubectl -n staging get svc api -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
PROD=$(kubectl -n prod get svc api -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
```

**terraform-eks-apply.png**: the cluster resources in state, the flag on.

```bash
cd terraform/backend && terraform state list | grep -E 'eks|launch_template|ec2_tag' && terraform output | grep eks_; cd ../..
```

**eks-nodes-ready.png**: two nodes on the EKS kubelet build, metrics-server up.

```bash
kubectl get nodes -o wide && kubectl -n kube-system get deploy metrics-server
```

**eks-two-namespaces.png**: same image, two namespaces, one ELB each.

```bash
kubectl get svc,deploy,hpa -A | grep -v kube-system
curl -s http://$STAGING:8080/api/version/; echo; curl -s http://$PROD/api/version/; echo
```

**eks-elb-readyz.png**: database and storage ok from inside a pod on the node role, through the load balancer.

```bash
curl -s http://$PROD/readyz/; echo
kubectl -n prod exec deploy/api -- curl -s -m 2 http://169.254.169.254/latest/meta-data/iam/security-credentials/; echo
```

**eks-rollback-version-check.png**: back one revision on prod, verified from outside.

```bash
deploy/bin/rollback.sh prod
kubectl -n prod rollout history deployment/api
```

**eks-hpa-metrics.png**: the HPA reading real CPU through metrics-server.

```bash
kubectl -n prod get hpa && kubectl top pods -n prod
```

**eks-rds-ingress.png**: the RDS group admits both node groups and nothing else.

```bash
aws ec2 describe-security-groups --group-ids sg-0a6cbcfad983c95b1 --query 'SecurityGroups[0].IpPermissions[].[FromPort,UserIdGroupPairs[0].GroupId]' --output table
```

## Jenkins, once the stages are merged and a build has run

**jenkins-stage-view-green.png**: the stage view of a main build, all stages green, prod included. This is the body screenshot for the whole pipeline.

**jenkins-junit-api-tests.png**: the build's Tests tab showing the 10 unit and integration rows plus the 2 smoke rows per environment.

**jenkins-console-deploy-staging.png**: the `API: deploy staging` console, from `Added new context` and `job.batch/migrate condition met` through `answering at http://...elb.amazonaws.com:8080` and `2 passed`.

**jenkins-red-stops-before-prod.png**: push a commit that breaks a test (flip an assert in `test_money.py`), let it run, capture the stage view with `API: test` red and every later stage skipped, then revert. Pair it with the failure email in **jenkins-failure-email.png**.

**jenkins-prod-skipped-on-branch.png**: a build from `dev/backend` showing `API: deploy prod` skipped by the `when` condition.

## If the lab session ended in between

Credentials and the node are gone until you restart:

```bash
aws ec2 start-instances --instance-ids i-0c8ceb9bdc37f5f4b >/dev/null
aws ec2 wait instance-running --instance-ids i-0c8ceb9bdc37f5f4b && sleep 60 && kubectl get nodes
```

The EKS control plane keeps running; only the nodes need bringing back if
they were scaled to zero before the session ended:

```bash
aws eks update-nodegroup-config --cluster-name rmit-store-eks --nodegroup-name rmit-store-eks-nodes --scaling-config minSize=2,maxSize=3,desiredSize=2
KUBECONFIG=$PWD/deploy/ansible/eks.kubeconfig kubectl get nodes -w     # two Ready in about two minutes
```