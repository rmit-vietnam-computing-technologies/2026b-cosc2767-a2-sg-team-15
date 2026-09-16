#!/bin/bash
# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 13/09/2026
# Last modified: 14/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author rehearsed it
#   on k3s. Reference: kubectl rollout undo,
#   https://kubernetes.io/docs/reference/kubectl/generated/kubectl_rollout/kubectl_rollout_undo/

# Back to the previous build in one environment, then prove it from outside
# via /api/version/. Migrations are additive and stay; the code is what moves.
#
#     KUBECONFIG=... deploy/bin/rollback.sh <staging|prod>

set -euo pipefail
ENV=${1:?usage: rollback.sh <staging|prod>}
cd "$(dirname "$0")/../.."

. deploy/bin/lib.sh
BASE_URL=$(base_url "$ENV")

kubectl -n "$ENV" rollout undo deployment/api
kubectl -n "$ENV" rollout status deployment/api --timeout=180s

IMAGE=$(kubectl -n "$ENV" get deployment api -o jsonpath='{.spec.template.spec.containers[0].image}')
WANT=${IMAGE##*:}
for _ in $(seq 1 20); do
  GOT=$(curl -sf "$BASE_URL/api/version/" | sed -n 's/.*"commit":"\([^"]*\)".*/\1/p')
  [ "$GOT" = "$WANT" ] && { echo "rolled back $ENV to $IMAGE, /api/version/ reports $GOT"; exit 0; }
  sleep 3
done
echo "rollback finished but /api/version/ reports $GOT, expected $WANT"; exit 1
