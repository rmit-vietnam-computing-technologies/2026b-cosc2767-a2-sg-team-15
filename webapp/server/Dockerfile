# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 07/09/2026
# Last modified: 07/09/2026
# Acknowledgement: Containerises the process performed by hand in
#   docs/runbooks/plan-b-ec2.md and automated in deploy/plan-c/roles/api.
#   Drafted with Claude (Anthropic) in a guided session; the author built,
#   ran and verified the image. References: Dockerfile reference,
#   https://docs.docker.com/reference/dockerfile/; multi-stage builds,
#   https://docs.docker.com/build/building/multi-stage/; gunicorn settings,
#   https://docs.gunicorn.org/en/stable/settings.html; Django static files,
#   https://docs.djangoproject.com/en/5.2/howto/static-files/deployment/

#  The API tier as an image.
#
# Three stages. `builder` resolves dependencies, `runtime` is what ships,
# `test` layers the suite on top of runtime so CI tests the exact bytes that
# deploy. Always name the target: with no --target, Docker builds the LAST
# stage in the file, and that is test, because test must come after the
# runtime it derives from.
#
#     docker build --target runtime -t rmit-store-api:$(git rev-parse --short HEAD) \
#         --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) server/
#     docker build --target test -t rmit-store-api-test server/
#
# A test image started by mistake fails loudly -- its CMD is pytest, not
# gunicorn -- so the wrong target cannot quietly serve traffic.
#
# What the image deliberately does NOT do: run migrations. `migrate` is a
# separate invocation of this same image, ordered by whatever runs it, so two
# replicas can never race to apply the same schema change. That decision is
# on record in docs/adr/0002-database-topology.md and it does not change
# because the process is now in a container.

# One interpreter everywhere. 3.14 is what the suite has been run on and what
# Django 5.2.8+ supports; pinning it here retires the drift between the
# laptop (3.14) and the Plan C instances (3.11). The patch level floats on
# purpose so a rebuild picks up interpreter security fixes; a digest pin is a
# Plan F decision.
ARG PYTHON_VERSION=3.14


# ---------------------------------------------------------------------------
# builder: resolve and install dependencies into a self-contained venv
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# A venv rather than a system install, so the whole dependency tree is one
# directory that copies cleanly into the runtime stage and nothing from the
# build ever leaks alongside it.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Requirements first, source later: this layer is cached until
# requirements.txt changes, so an application edit does not reinstall Django.
WORKDIR /app
COPY requirements.txt ./
# Every dependency ships a binary wheel (psycopg[binary] bundles libpq,
# Pillow bundles its codecs), so no compiler or -dev packages are needed.
RUN pip install -r requirements.txt


# ---------------------------------------------------------------------------
# runtime: what ships
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

# [ADV-3] The build that is running, baked in at build time so
# GET /api/version/ cannot disagree with the image tag. Both remain ordinary
# environment variables and can still be overridden at run time.
ARG APP_VERSION=1.0.0
ARG GIT_COMMIT=unknown

LABEL org.opencontainers.image.title="RMIT Store API" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

#  DJANGO_SETTINGS_MODULE is fixed to prod in the
# image, not read from a file. config/wsgi.py consults it before anything has
# parsed a .env, and prod refuses to boot without a real SECRET_KEY and
# ALLOWED_HOSTS -- so a container started with no configuration fails loudly
# at start rather than serving DEBUG pages. The values arrive through
# --env-file or the orchestrator, never through a file in the image.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    APP_VERSION="${APP_VERSION}" \
    GIT_COMMIT="${GIT_COMMIT}"

#  gunicorn reads WEB_CONCURRENCY natively for --workers, so the
# worker count is a plain environment variable and no entrypoint script is
# needed to compute it. 3 matches the Plan C value for a t3.small; override
# per environment.
ENV WEB_CONCURRENCY=3

WORKDIR /app

# An unprivileged user for the process. UID 1000 on purpose: it is the first
# user on most laptops, so files written into a bind mount on a developer
# machine (test-reports/, for one) come out owned by the developer.
#
# /app/media is created here so that when a named volume is mounted over it
# for the first time, Docker copies the directory's ownership into the
# volume and the application can write uploads without a chown step.
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/media \
    && chown -R app:app /app

COPY --from=builder /opt/venv /opt/venv

# Explicit copies, not `COPY . .`: this list is the complete answer to "what
# is in the image". Tests, dev requirements, the virtualenv and any .env are
# absent by construction, not by remembering to ignore them.
COPY --chown=app:app manage.py ./
COPY --chown=app:app config ./config
COPY --chown=app:app apps ./apps
COPY --chown=app:app templates ./templates
# 47 product photographs, read by `manage.py seed_demo` from BASE_DIR.
COPY --chown=app:app seed_assets ./seed_assets

# Numeric rather than `app`, so an orchestrator that enforces non-root can
# verify it from the image config without resolving /etc/passwd.
USER 1000:1000

#  collectstatic belongs to the build, not the
# entrypoint: its output is identical on every replica and never changes
# after the image is built (docs/adr/0003-media-storage.md). It must run
# under the SAME settings module as the server -- prod writes the whitenoise
# manifest that prod needs at request time; dev does not -- so the throwaway
# values below exist only to satisfy prod's boot guard. Nothing connects to a
# database here.
RUN SECRET_KEY=build-time-only-never-used-at-runtime \
    ALLOWED_HOSTS=build \
    python manage.py collectstatic --noinput

EXPOSE 8000

#  Liveness, not readiness. The image-level check is what an
# orchestrator uses to decide whether to restart the task, and /healthz/
# touches nothing -- a probe that checked the database would restart a
# healthy process because the database was slow. Compose overrides this with
# /readyz/ where the question is "may the web tier be pointed at it yet",
# which is a different question with a different answer.
#
# python's urllib rather than curl, which the slim image does not ship. Any
# non-2xx raises, and an exception is a non-zero exit.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=2)"]

#  bind 0.0.0.0 -- the container namespace is the
# boundary, not loopback. Nothing publishes this port; the web tier reaches
# it over the container network.
#
# --forwarded-allow-ips '*' is the one difference from the Plan C command
# line. There, nginx and gunicorn shared a host and the proxy arrived from
# 127.0.0.1, which gunicorn trusts by default. Here the proxy is another
# container and never loopback, so without this gunicorn discards the
# X-Forwarded-* headers the web tier sends. The same reasoning as the bind:
# only the web tier can reach this socket.
#
# --no-control-socket: gunicorn 25.1 and later open a management socket by
# default, under $XDG_RUNTIME_DIR or $HOME/.gunicorn/. Neither exists for
# this user, so every boot logged an ERROR before serving normally. Nothing
# runs gunicornc inside a container -- the orchestrator scales replicas, not
# workers -- so the interface is disabled rather than given somewhere to
# live. The flag needs gunicorn >= 25.1, which the dependency lock pins.
#
# Logs to stdout and stderr so the container runtime collects them, which is
# the shape a log shipper expects (ADV-4).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--forwarded-allow-ips", "*", "--no-control-socket", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "--capture-output"]


# ---------------------------------------------------------------------------
# test: the suite, layered on the exact runtime bytes
# ---------------------------------------------------------------------------
# [T15-BE-TEST][REQ-3][REQ-5] Built from runtime rather than from builder so
# the code under test is byte-for-byte the code that deploys. It is never
# pushed to a registry; it exists for `docker build --target test` and the
# CI compose overlay. It needs a PostgreSQL to run against -- pytest-django
# creates the test database from DATABASE_URL -- which is why it is run
# through compose, not at build time.
FROM runtime AS test

# Root only long enough to add the dev tooling to the venv.
#
# Both files: requirements-dev.txt begins with `-r requirements.txt`, and the
# runtime stage deliberately does not carry the runtime requirements file.
USER root
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY --chown=app:app pytest.ini .coveragerc ./
COPY --chown=app:app tests ./tests
RUN mkdir -p /app/test-reports && chown app:app /app/test-reports
USER 1000:1000

# The runtime stage sets DJANGO_SETTINGS_MODULE=config.settings.prod, and
# pytest-django gives the environment variable precedence over pytest.ini.
# Left alone, the suite would inherit prod settings and die on the SECRET_KEY
# guard before collecting a single test. This override restores the value
# pytest.ini already names, so the two agree.
ENV DJANGO_SETTINGS_MODULE=config.settings.test

# The coverage gate lives on the command line and not in pytest.ini, for the
# reasons given there. This is the CI invocation; a developer running a
# marker subset inside the container can still override the command.
CMD ["pytest", "--cov-fail-under=65"]