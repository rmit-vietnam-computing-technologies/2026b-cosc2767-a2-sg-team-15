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
#   verified it. Reference: aws ssm get-parameters-by-path,
#   https://docs.aws.amazon.com/cli/latest/reference/ssm/get-parameters-by-path.html

# Sourced by deploy.sh and smoke.sh.

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
