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
NAMESPACE="staging"
# ---------------------------------------------

# Path to the manifest template, relative to this script's own location -
# adjust if your directory layout differs (e.g. deploy/bin/ + deploy/manifests/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_TEMPLATE="${SCRIPT_DIR}/../k8s/base/frontend-deployment.yaml"

if [[ ! -f "${MANIFEST_TEMPLATE}" ]]; then
  echo "Error: manifest template not found at ${MANIFEST_TEMPLATE}" >&2
  exit 1
fi

kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"

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

RENDERED_MANIFEST="$(mktemp)"
trap 'rm -f "${RENDERED_MANIFEST}"' EXIT

sed \
  -e "s|__IMAGE__|${IMAGE}|g" \
  -e "s|__NAME__|${DEPLOYMENT_NAME}|g" \
  "${MANIFEST_TEMPLATE}" > "${RENDERED_MANIFEST}"

echo "Applying manifest (creates the Deployment if it doesn't exist yet, updates it otherwise)..."
kubectl apply -f "${RENDERED_MANIFEST}" -n "${NAMESPACE}"

echo "Waiting for rollout..."
kubectl rollout status "deployment/${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --timeout=180s
