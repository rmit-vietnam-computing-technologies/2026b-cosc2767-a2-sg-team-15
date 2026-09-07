# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 07/09/2026
# Last modified: 07/09/2026
# Acknowledgement: Containerises the web role in deploy/plan-c/roles/web,
#   which performs these steps on an instance. Drafted with Claude (Anthropic)
#   in a guided session; the author built, ran and verified the image.
#   References: Vite, "Deploying a Static Site",
#   https://vite.dev/guide/static-deploy; the nginx image's environment
#   templates, https://hub.docker.com/_/nginx ("Using environment variables
#   in nginx configuration"); multi-stage builds,
#   https://docs.docker.com/build/building/multi-stage/

#  The web tier as an image.
#
# Two stages. `build` compiles the SPA with the same Node major the Plan C
# web role installs; `runtime` is nginx serving the result and proxying
# everything Django-shaped to the API tier. The final image carries no Node,
# no npm and no source -- the brief's hard requirement, and the concrete fix
# for the Plan C limitation of compiling a frontend on a production box.
#
#     docker build -t rmit-store-web:$(git rev-parse --short HEAD) \
#         --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) client/
#
# Only one stage ships, so no --target is needed here.

ARG NODE_VERSION=22
ARG NGINX_VERSION=1.30


# ---------------------------------------------------------------------------
# build: compile the bundle
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS build

WORKDIR /app

# Lockfile first so this layer is cached until a dependency changes. `npm ci`
# installs exactly what package-lock.json says and refuses to run if the two
# files disagree -- the property `npm install` lacks.
#
# NODE_ENV is deliberately NOT set to production here: npm would then skip
# devDependencies, and vite, the Vue plugin and sass are all devDependencies.
# Vite selects production mode for `vite build` on its own.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Explicit copies, as in the API image: the build input is enumerable, and
# no .env from a laptop can reach it.
COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src

# Vite copies public/ into dist/ byte-for-byte, so dist/config.js is the
# upstream runtime configuration file, unhashed and editable in place.
RUN npm run build


# ---------------------------------------------------------------------------
# runtime: nginx serving the bundle and fronting the API
# ---------------------------------------------------------------------------
FROM nginx:${NGINX_VERSION}-alpine AS runtime

ARG APP_VERSION=1.0.0
ARG GIT_COMMIT=unknown

LABEL org.opencontainers.image.title="RMIT Store web" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

# Where the API tier is, as host:port, substituted
# into the site configuration when the container starts. One image, three
# deployments:
#
#   Compose          api:8000                  the service name
#   two instances    <api-private-ip>:8000     from the instance's env file
#   Swarm            api:8000                  the service name again
#
# The nginx image's entrypoint renders /etc/nginx/templates/*.template into
# /etc/nginx/conf.d/ with envsubst before nginx starts, substituting only
# variables that are set in the environment -- so nginx's own $host, $uri
# and friends in the template are left alone.
ENV API_UPSTREAM=api:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# The whole of dist/: index.html, the hashed bundle under assets/, the
# images, and config.js.
#
# config.js is served as built, with API_BASE_URL set
# to the relative "/api". That is correct in every environment, because this
# nginx proxies /api/ itself and the browser only ever sees one origin. The
# runtime-configuration mechanism is still there for the day it is needed:
# mount a different file over /usr/share/nginx/html/config.js and no rebuild
# is required, which is the whole point of the design.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# Liveness of nginx itself, not of the API behind it. A web
# tier whose API is down should be alive and returning 502, so the failure is
# visible at the edge, not hidden behind a restarting proxy.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "--spider", "http://127.0.0.1/"]
