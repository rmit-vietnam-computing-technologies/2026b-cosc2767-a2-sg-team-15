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
#   verified it. Reference: Compose run,
#   https://docs.docker.com/reference/cli/docker/compose/run/

# Build the test image for this commit and run the suite against a throwaway
# Postgres. JUnit and coverage XML land in webapp/server/test-reports/.
#
#     deploy/bin/test.sh <tag>

set -euo pipefail
TAG=${1:?usage: test.sh <tag>}
cd "$(dirname "$0")/../.."
export HOST_UID="${HOST_UID:-$(id -u)}"
export HOST_GID="${HOST_GID:-$(id -g)}"

# Compose refuses to start without these; the values do not matter for tests.
[ -f .env ] || printf 'SECRET_KEY=ci-only\nPOSTGRES_PASSWORD=ci-only\nSEED_ADMIN_PASSWORD=ci-only\n' > .env

# Pre-create as the current user, or the daemon makes it root-owned.
mkdir -p webapp/server/test-reports

export GIT_COMMIT="$TAG"
docker compose -f compose.yaml -f compose.ci.yaml build test
docker compose -f compose.yaml -f compose.ci.yaml run --rm test
docker compose -f compose.yaml -f compose.ci.yaml down
