# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 07/09/2026
# Last modified: 14/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author built, ran and verified the image. References: Dockerfile reference,
#   https://docs.docker.com/reference/dockerfile/; multi-stage builds,
#   https://docs.docker.com/build/building/multi-stage/; non-root nginx,
#   https://hub.docker.com/r/nginxinc/nginx-unprivileged

# The API tier: nginx on 80 in front of gunicorn on loopback, one image.
# Stages: builder (deps), runtime (ships), test (suite on top of runtime).
#
#     docker build --target runtime -t rmit-store-api:<sha> --build-arg GIT_COMMIT=<sha> webapp/server/
#
# Migrations never run here. `migrate` is a separate run of this image.

ARG PYTHON_VERSION=3.14


# --- builder ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt


# --- runtime ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG APP_VERSION=1.0.0
ARG GIT_COMMIT=unknown

LABEL org.opencontainers.image.title="RMIT Store API" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    APP_VERSION="${APP_VERSION}" \
    GIT_COMMIT="${GIT_COMMIT}" \
    WEB_CONCURRENCY=1 \
    GUNICORN_THREADS=4

# nginx plus setcap so it can bind 80 as the app user.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx libcap2-bin \
    && rm -rf /var/lib/apt/lists/* \
    && setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx

WORKDIR /app

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/media \
    && chown -R app:app /app /var/lib/nginx /var/log/nginx

COPY --from=builder /opt/venv /opt/venv

COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh

# Explicit copies: tests, dev requirements and .env never enter the image.
COPY --chown=app:app manage.py ./
COPY --chown=app:app config ./config
COPY --chown=app:app apps ./apps
COPY --chown=app:app templates ./templates
COPY --chown=app:app seed_assets ./seed_assets

USER 1000:1000

# collectstatic under prod settings so the whitenoise manifest exists.
# The two values only satisfy prod's boot guard.
RUN SECRET_KEY=build-time-only-never-used-at-runtime \
    ALLOWED_HOSTS=build \
    python manage.py collectstatic --noinput

EXPOSE 80

# Through nginx, so a dead nginx or a dead gunicorn both show up.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1/healthz/', timeout=2)"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]


# --- test ------------------------------------------------------------------
# Built from runtime so CI tests the bytes that deploy. Never pushed.
FROM runtime AS test

USER root
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY --chown=app:app pytest.ini .coveragerc ./
COPY --chown=app:app tests ./tests
RUN mkdir -p /app/test-reports # && chown app:app /app/test-reports
# USER 1000:1000

ENV DJANGO_SETTINGS_MODULE=config.settings.test

CMD ["pytest"]
