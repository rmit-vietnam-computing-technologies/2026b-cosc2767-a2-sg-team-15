#!/usr/bin/env bash
# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 15/09/2026
# Last modified: 15/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it. Reference: bash BASH_SOURCE and return in sourced files,
#   https://www.gnu.org/software/bash/manual/html_node/Bash-Builtins.html

# Source this, do not run it:
#
#     . deploy/bin/env.sh          # eks, the default
#     . deploy/bin/env.sh k3s      # the fallback cluster
#
# Sets what every script in deploy/bin expects, checks the lab credentials
# still work, and prints the nodes and the load balancers. Safe to source
# again. A new terminal has none of this; deploy.sh quitting at its usage
# line or kubectl talking to localhost:8080 means it was not sourced here.

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  echo "source this file, do not run it:  . deploy/bin/env.sh [eks|k3s]" >&2
  exit 1
fi

_root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "not inside the repo" >&2; return 1; }
_cluster=${1:-eks}
case "$_cluster" in
  eks|k3s) ;;
  *) echo "usage: . deploy/bin/env.sh [eks|k3s]" >&2; return 1 ;;
esac

export AWS_PAGER=""
export GIT_PAGER=cat
export AWS_REGION=${AWS_REGION:-us-east-1}
export KUBECONFIG="$_root/deploy/ansible/$_cluster.kubeconfig"

# Stale Learner Lab keys fail here, before anything else gets a chance to.
_account=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) \
  || { echo "AWS credentials rejected; paste today's Learner Lab CLI block into ~/.aws/credentials" >&2; return 1; }
export ECR_REPO="$_account.dkr.ecr.$AWS_REGION.amazonaws.com/rmit-store-api"

# The commit to deploy. TAG=<tag> . deploy/bin/env.sh picks an existing one.
TAG=${TAG:-$(git -C "$_root" rev-parse --short HEAD)}

echo "cluster=$_cluster  account=$_account  region=$AWS_REGION  TAG=$TAG"
if [ -f "$KUBECONFIG" ]; then
  kubectl get nodes 2>/dev/null \
    && kubectl get svc -A --field-selector spec.type=LoadBalancer 2>/dev/null \
    || echo "cluster not reachable; session ended? see the end of deploy/README.md" >&2
else
  echo "no $KUBECONFIG yet; deploy/README.md section 2 makes it" >&2
fi

unset _root _cluster _account
