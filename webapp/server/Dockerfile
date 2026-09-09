# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 07/09/2026
# Last modified: 09/09/2026
# Acknowledgement: Containerises the process automated in deploy/plan-c/roles/api.
#   Drafted with Claude (Anthropic) in a guided session; the author built,
#   ran and verified the image. References: Dockerfile reference,
#   https://docs.docker.com/reference/dockerfile/; multi-stage builds,
#   https://docs.docker.com/build/building/multi-stage/; gunicorn settings,
#   https://docs.gunicorn.org/en/stable/settings.html

# The API tier as an image.
#
# Three stages: builder (dependencies), runtime (what ships), test (the suite
# on top of runtime, so CI tests the bytes that deploy). Always pass --target;
# the last stage in the file is test.
#
#     docker build --target runtime -t rmit-store-api:<sha> --build-arg GIT_COMMIT=<sha> webapp/server/
#
# Migrations are NOT run here. `migrate` is a separate invocation of this
# image so two replicas never race on the schema (see the migrate service
# in compose.yaml).

ARG PYTHON_VERSION=3.14


# ---------------------------------------------------------------------------
# builder
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# A venv so the dependency tree is one directory to copy into runtime.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Requirements before source: this layer is cached until requirements.txt changes.
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt


# ---------------------------------------------------------------------------
# runtime
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

# Build identity, baked in so GET /api/version/ matches the image tag.
ARG APP_VERSION=1.0.0
ARG GIT_COMMIT=unknown

LABEL org.opencontainers.image.title="RMIT Store API" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

# Settings fixed to prod; prod refuses to boot without
# a real SECRET_KEY and ALLOWED_HOSTS, which arrive from the environment.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    APP_VERSION="${APP_VERSION}" \
    GIT_COMMIT="${GIT_COMMIT}"

# gunicorn reads WEB_CONCURRENCY for --workers.
ENV WEB_CONCURRENCY=3

WORKDIR /app

# Unprivileged user. UID 1000 so files written to bind mounts belong to the
# developer; /app/media pre-created so a named volume inherits its ownership.
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/media \
    && chown -R app:app /app

COPY --from=builder /opt/venv /opt/venv

# Explicit copies, not `COPY . .`: tests, dev requirements and .env are absent
# by construction.
COPY --chown=app:app manage.py ./
COPY --chown=app:app config ./config
COPY --chown=app:app apps ./apps
COPY --chown=app:app templates ./templates
COPY --chown=app:app seed_assets ./seed_assets

USER 1000:1000

# collectstatic at build time, under the same settings
# module as the server (prod writes the whitenoise manifest). The values only
# satisfy prod's boot guard; nothing connects to a database.
RUN SECRET_KEY=build-time-only-never-used-at-runtime \
    ALLOWED_HOSTS=build \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Liveness only; /healthz/ touches nothing. Compose overrides
# with /readyz/ where the question is whether the web tier may point at it.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=2)"]

# bind 0.0.0.0: the container network is the boundary.
# --forwarded-allow-ips '*': the proxy is another container, not loopback.
# --no-control-socket: gunicorn >= 25.1 opens one by default and this user
# has nowhere to put it. Logs to stdout/stderr for the container runtime.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--forwarded-allow-ips", "*", "--no-control-socket", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "--capture-output"]


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------
# Built from runtime so the code under test is the
# code that deploys. Never pushed; run via compose.ci.yaml, which supplies
# the PostgreSQL pytest-django needs.
FROM runtime AS test

USER root
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY --chown=app:app pytest.ini .coveragerc ./
COPY --chown=app:app tests ./tests
RUN mkdir -p /app/test-reports && chown app:app /app/test-reports
USER 1000:1000

# The environment variable outranks pytest.ini; restore the test settings.
ENV DJANGO_SETTINGS_MODULE=config.settings.test

# The coverage gate is here rather than in pytest.ini so marker subsets run green locally.
CMD ["pytest", "--cov-fail-under=60"]
