#!/bin/bash
# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 13/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author built, ran and
#   verified it. References: gunicorn settings,
#   https://docs.gunicorn.org/en/stable/settings.html; bash wait -n,
#   https://www.gnu.org/software/bash/manual/html_node/Job-Control-Builtins.html

# Runs gunicorn and nginx together. If either exits, the container exits and
# the orchestrator restarts it. Any argument replaces the servers, so
# `migrate`, `seed_demo` and `pytest` run in the same image.

set -euo pipefail

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

# One worker per replica by default; scale with replicas so per-process
# metrics stay consistent. Threads handle the concurrency instead.
gunicorn config.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers "${WEB_CONCURRENCY:-1}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout 60 \
    --no-control-socket \
    --error-logfile - \
    --capture-output &
GUNICORN=$!

nginx -g 'daemon off;' &
NGINX=$!

stop() {
    kill -TERM "$GUNICORN" 2>/dev/null || true
    kill -QUIT "$NGINX" 2>/dev/null || true
}
trap stop TERM INT

CODE=0
wait -n || CODE=$?
stop
wait
exit "$CODE"
