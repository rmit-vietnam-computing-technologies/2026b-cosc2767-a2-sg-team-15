#!/bin/bash
# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 14/09/2026
# Last modified: 14/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it. References: aws ssm get-parameters-by-path,
#   https://docs.aws.amazon.com/cli/latest/reference/ssm/get-parameters-by-path.html;
#   kubectl jsonpath, https://kubernetes.io/docs/reference/kubectl/jsonpath/

# Sourced by deploy.sh, smoke.sh and rollback.sh.

# secret_env_file <env> <outfile>
# Writes KEY=VALUE lines for the environment's secrets to <outfile>.
# SECRET_FILE, if set, is the manual override; otherwise SSM Parameter Store
# under /rmit-store/<env>/, written by terraform/backend.
secret_env_file() {
  local env=$1 out=$2
  if [ -n "${SECRET_FILE:-}" ]; then
    [ -f "$SECRET_FILE" ] || { echo "SECRET_FILE=$SECRET_FILE not found" >&2; return 1; }
    grep -v '^\s*#' "$SECRET_FILE" | grep '=' > "$out"
    return
  fi
  aws ssm get-parameters-by-path --path "/rmit-store/$env" --with-decryption \
    --region "${AWS_REGION:-us-east-1}" \
    --query 'Parameters[].[Name,Value]' --output text \
    | awk -F'\t' '{ n=$1; sub(/.*\//, "", n); print n "=" $2 }' > "$out"
  [ -s "$out" ] || { echo "no parameters under /rmit-store/$env; run terraform apply in terraform/backend" >&2; return 1; }
}

# base_url <env>
# Where the environment answers from outside. A cloud load balancer gives
# the Service a hostname (EKS: one classic ELB per namespace) and that wins,
# waiting up to two minutes for it to appear. k3s ServiceLB only reports the
# node's private IP, so there the SMOKE_BASE_URL line in the config file is
# the answer, as it is when kubectl cannot reach a cluster at all.
base_url() {
  local env=$1 svc port host ip
  for _ in $(seq 1 24); do
    svc=$(kubectl -n "$env" get svc api \
      -o jsonpath='{.spec.ports[0].port}|{.status.loadBalancer.ingress[0].hostname}|{.status.loadBalancer.ingress[0].ip}' 2>/dev/null) || break
    IFS='|' read -r port host ip <<< "$svc"
    [ -n "$host" ] && { echo "http://$host:$port"; return; }
    [ -n "$ip" ] && break
    sleep 5
  done
  grep '^SMOKE_BASE_URL=' "deploy/k8s/$env.config.env" | cut -d= -f2-
}

# wait_for_http <base_url>
# Polls /healthz/ until it answers, up to three minutes. A fresh load
# balancer needs a minute or two to register the nodes; k3s answers at once.
wait_for_http() {
  local url=$1
  for _ in $(seq 1 36); do
    curl -sf --max-time 5 "$url/healthz/" >/dev/null && return 0
    sleep 5
  done
  echo "$url/healthz/ still not answering after three minutes" >&2
  return 1
}
