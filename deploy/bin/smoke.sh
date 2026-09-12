#!/bin/bash
# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 13/09/2026
# Last modified: 14/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified it. Reference: pytest -m,
#   https://docs.pytest.org/en/stable/example/markers.html

# Post-deploy checks against a live environment, from the test image built by
# test.sh. Fails if the running commit is not the one just deployed.
#
#     deploy/bin/smoke.sh <staging|prod> <tag>

set -euo pipefail
ENV=${1:?usage: smoke.sh <staging|prod> <tag>}
TAG=${2:?usage: smoke.sh <staging|prod> <tag>}
cd "$(dirname "$0")/../.."

K8S=deploy/k8s
. deploy/bin/lib.sh
SECRETS=$(mktemp); trap 'rm -f "$SECRETS"' EXIT
secret_env_file "$ENV" "$SECRETS"
BASE_URL=$(grep '^SMOKE_BASE_URL=' "$K8S/$ENV.config.env" | cut -d= -f2-)
MEMBER_EMAIL=$(grep '^SEED_ADMIN_EMAIL=' "$SECRETS" | cut -d= -f2-)
MEMBER_PASSWORD=$(grep '^SEED_ADMIN_PASSWORD=' "$SECRETS" | cut -d= -f2-)

mkdir -p webapp/server/test-reports
docker run --rm \
  -e SMOKE_BASE_URL="$BASE_URL" \
  -e SMOKE_EXPECTED_COMMIT="$TAG" \
  -e SMOKE_MEMBER_EMAIL="$MEMBER_EMAIL" \
  -e SMOKE_MEMBER_PASSWORD="$MEMBER_PASSWORD" \
  -v "$PWD/webapp/server/test-reports:/app/test-reports" \
  "rmit-store-api-test:$TAG" \
  pytest -m smoke --no-cov --junitxml="test-reports/smoke-$ENV.xml"
