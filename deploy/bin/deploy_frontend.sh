#!/usr/bin/env bash
# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Bao Nguyen Pham Gia
# ID: s4143691
# Created  date: 16/09/2026
# Last modified: 16/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) (yes, I gave in to the AI slop.)

#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: ECR_REPO=<repo-url> $0 <deployment-name> <image-tag>" >&2
  exit 1
fi

if [[ -z "${ECR_REPO:-}" ]]; then
  echo "Error: ECR_REPO environment variable must be set" >&2
  exit 1
fi

DEPLOYMENT_NAME="$1"
IMAGE_TAG="$2"

# --- Adjust these to match your actual setup ---
CLUSTER_NAME="frontend_cluster"
REGION="us-east-1"                 # match wherever the lab actually provisions
NAMESPACE=$DEPLOYMENT_NAME
CONTAINER_NAME="${DEPLOYMENT_NAME}" # override below if the container name inside the pod spec differs
# -------------------------------------------------

IMAGE="${ECR_REPO}:${IMAGE_TAG}"

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

kubectl config use-context "${CLUSTER_NAME}"

kubectl set image "deployment/${DEPLOYMENT_NAME}" \
  "${CONTAINER_NAME}=${IMAGE}" \
  -n "${NAMESPACE}"

echo "Waiting for rollout..."
kubectl rollout status "deployment/${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --timeout=180s
