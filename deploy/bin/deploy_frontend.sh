#!/bin/bash
# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: <>
# ID: s3926310
# Created  date: 13/09/2026
# Last modified: 14/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it on k3s and EKS. References: kubectl create secret,
#   https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret_docker-registry/;
#   kubectl rollout, https://kubernetes.io/docs/reference/kubectl/generated/kubectl_rollout/

# Deploy one build to one environment: config and secrets, migrate once,
# then roll the Deployment and wait for it.
#
#     ECR_REPO=... KUBECONFIG=... deploy/bin/deploy.sh <staging|prod> <tag>
#
# Secrets come from SSM Parameter Store (/rmit-store/<env>/*), or from a
# file if SECRET_FILE is set.

set -euo pipefail
ENV=${1:?usage: deploy.sh <staging|prod> <tag>}
TAG=${2:?usage: deploy.sh <staging|prod> <tag>}
: "${ECR_REPO:?ECR_REPO is required}"
AWS_REGION=${AWS_REGION:-us-east-1}
cd "$(dirname "$0")/../.."

K8S=deploy/k8s
NS=$ENV
IMAGE="$ECR_REPO:$TAG"
. deploy/bin/lib.sh
SECRETS=$(mktemp); trap 'rm -f "$SECRETS"' EXIT
secret_env_file "$ENV" "$SECRETS"

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

# ECR token lasts 12h; refreshed on every deploy. Cached images keep pods alive past that.
kubectl -n "$NS" create secret docker-registry ecr-pull \
  --docker-server="${ECR_REPO%%/*}" --docker-username=AWS \
  --docker-password="$(aws ecr get-login-password --region "$AWS_REGION")" \
  --dry-run=client -o yaml | kubectl apply -f -

# Then the code.
kubectl kustomize "$K8S/overlays/$ENV" \
  | sed "s|IMAGE_PLACEHOLDER|$IMAGE|; s|CONFIG_HASH_PLACEHOLDER|$CONFIG_HASH|" | kubectl apply -f -
kubectl -n "$NS" rollout status deployment/api --timeout=180s
kubectl -n "$NS" get pods -o wide

# Not done until it answers from outside. On EKS this is where a new ELB
# spends its first minute or two.
URL=$(base_url "$NS")
wait_for_http "$URL"
echo "deployed $IMAGE to $NS, answering at $URL"
