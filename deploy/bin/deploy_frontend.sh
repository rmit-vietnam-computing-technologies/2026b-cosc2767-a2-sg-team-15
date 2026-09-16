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
NAMESPACE="${DEPLOYMENT_NAME}"
CONTAINER_NAME="frontend" # override below if the container name inside the pod spec differs
# -------------------------------------------------

# Assumes the caller has already pointed KUBECONFIG (or ~/.kube/config) at
# the right cluster - e.g. via `aws eks update-kubeconfig` run beforehand,
# as the Jenkins stage calling this script already does.
if [[ -z "${KUBECONFIG:-}" ]] && [[ ! -f "${HOME}/.kube/config" ]]; then
  echo "Error: no KUBECONFIG set and no ~/.kube/config found. Run 'aws eks update-kubeconfig' first." >&2
  exit 1
fi

IMAGE="${ECR_REPO}:${IMAGE_TAG}"

echo "Target namespace:  ${NAMESPACE}"
echo "Deploying image:   ${IMAGE}"

kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"

kubectl set image "deployment/${DEPLOYMENT_NAME}" \
  "${CONTAINER_NAME}=${IMAGE}" \
  -n "${NAMESPACE}"

echo "Waiting for rollout..."
kubectl rollout status "deployment/${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --timeout=180s
