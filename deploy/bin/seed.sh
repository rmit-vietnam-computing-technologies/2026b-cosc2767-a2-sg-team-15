#!/bin/bash
# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 13/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it on k3s. Reference: Jobs,
#   https://kubernetes.io/docs/concepts/workloads/controllers/job/

# Load the demo catalogue and accounts into one environment. Run once per
# environment after the first deploy; safe to repeat.
#
#     ECR_REPO=... KUBECONFIG=... deploy/bin/seed.sh <staging|prod> <tag>

set -euo pipefail
ENV=${1:?usage: seed.sh <staging|prod> <tag>}
TAG=${2:?usage: seed.sh <staging|prod> <tag>}
: "${ECR_REPO:?ECR_REPO is required}"
cd "$(dirname "$0")/../.."

kubectl -n "$ENV" delete job seed --ignore-not-found --wait=true
sed "s|IMAGE_PLACEHOLDER|$ECR_REPO:$TAG|" deploy/k8s/jobs/seed.yaml | kubectl -n "$ENV" apply -f -
kubectl -n "$ENV" wait --for=condition=complete job/seed --timeout=300s
kubectl -n "$ENV" logs job/seed | tail -12
