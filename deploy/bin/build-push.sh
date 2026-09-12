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
#   verified it. Reference: ECR push,
#   https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html

# Build the runtime image once and push it tagged with the commit.
#
#     ECR_REPO=<account>.dkr.ecr.us-east-1.amazonaws.com/rmit-store-api deploy/bin/build-push.sh <tag>

set -euo pipefail
TAG=${1:?usage: build-push.sh <tag>}
: "${ECR_REPO:?ECR_REPO is required}"
AWS_REGION=${AWS_REGION:-us-east-1}
cd "$(dirname "$0")/../.."

REGISTRY=${ECR_REPO%%/*}
REPO_NAME=${ECR_REPO#*/}

aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$AWS_REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO_NAME" --region "$AWS_REGION" >/dev/null

docker build --target runtime -t "rmit-store-api:$TAG" --build-arg GIT_COMMIT="$TAG" webapp/server/
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker tag "rmit-store-api:$TAG" "$ECR_REPO:$TAG"
docker push "$ECR_REPO:$TAG"
echo "pushed $ECR_REPO:$TAG"
