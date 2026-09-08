<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 08/09/2026
Last modified: 08/09/2026
Acknowledgement: Structure follows Plan E of UPSTREAM-README.md and the Plan C
runbook in this directory. Drafted with Claude (Anthropic) in a guided session
from the terminal transcript of 07/09; the author performed every step, hit
every row of the troubleshooting table, and verified the result.
-->

# Plan E — run the RMIT Store as three containers with Compose

**This is the first time the two images meet.** Plan D built them and proved
each alone; here one command starts a database, applies the schema, brings up
the API, and puts nginx in front of it, in that order, and stops if any step
fails. No instance, no SSH, no Ansible: the laptop is the host.

> Timing from the real session: the first `up --build` is dominated by the two
> image builds and the `postgres:16-alpine` pull. With layers cached, the whole
> stack is serving in about 13 seconds — `db` healthy at 6.5 s, `migrate` exited
> at 7.4 s, `api` healthy at 13.0 s, `web` started at 13.1 s.

Angle-bracketed values like `<sha>` are placeholders, and `<repo>` is
wherever you cloned the repository. Substitute before pasting; bash reads
`<x>` as a file redirect.

---

## What changes from Plan C

Same three tiers, same nginx-in-front-of-gunicorn shape. The difference is
that nothing is installed anywhere: every tier is an image, and the network
between them is Docker's.

```
browser → :80  web      nginx: SPA from the image; proxies
                        /api /admin /healthz /readyz /static → api:8000
                        /media from the shared volume
                            ↓ compose network, resolved per request
               api      gunicorn :8000, 3 workers; whitenoise serves /static;
                        writes uploads to /app/media (the shared volume)
               db       postgres:16, data on the pgdata volume
               migrate  one-shot, same image as api, runs before api starts
               seed     one-shot, same image, only under --profile seed
```

Only `web` publishes a port. `db` and `api` are reachable on the compose
network and nowhere else — the posture the Plan C security groups enforce
with rules, expressed here by not writing a `ports:` line.

`config.js` still sets `API_BASE_URL` to the relative `/api`, and `web` still
forwards `Host` unchanged, for the same reasons as Plan C: one origin, and
product image URLs that work from a browser.

### Where this deliberately differs from Plan C and the upstream README

Six choices in Plan E are not what Plan C did or what `UPSTREAM-README.md`
describes. Each is a decision, not a drift.

1. **Migrations run in their own container, not in the API's entrypoint.**
   Plan E in the upstream README asks where migrations run when three
   containers start at once. Answer: in `migrate`, a one-shot service using
   the same image as `api` with a different command. `api` waits on
   `service_completed_successfully`. Two API replicas therefore never race to
   apply the same migration, because neither of them applies any. The API
   image itself has no migrate step anywhere —
   `docs/adr/0002-database-topology.md`.

2. **`/static/` is proxied to gunicorn, not served by nginx from disk.** In
   Plan C the API instance had nginx serving `staticfiles/` off disk. Here
   `collectstatic` ran inside the API image build, the files live in that
   image, and whitenoise serves them. The web tier has no copy and does not
   need one.

3. **The API address is resolved per request, not at nginx start.** Plan C
   used an `upstream` block: correct, because the address came from inventory
   and did not move. A container's address is not stable — recreate `api` and
   an `upstream` block keeps proxying to the old address until nginx is
   restarted. The web image's `nginx.conf.template` uses `resolver 127.0.0.11`
   and a variable in `proxy_pass` instead, at the cost of the keepalive pool.
   The address itself arrives as `API_UPSTREAM`, so the same image serves
   Compose, two instances and Swarm.

4. **Readiness in Compose, liveness in the image.** `server/Dockerfile`'s
   `HEALTHCHECK` hits `/healthz/`, the question an orchestrator restarts on.
   `compose.yaml` overrides it with `/readyz/`, the question "may `web` be
   pointed at it yet", which involves the database. The upstream README
   suggests exactly this use for the two endpoints.

5. **Seeding is a profile, with no marker file.** Plan C needed a marker
   because Ansible needed a changed/ok signal. `seed_demo` is idempotent by
   its own contract, so `docker compose --profile seed run --rm seed` is the
   whole mechanism, and a plain `up` can never seed.

6. **Uploads live on a named volume shared by `api` and `web`.** Correct for
   one host and one API replica per host; the moment there are two hosts
   there is no shared disk, and that is the S3 switch —
   `docs/adr/0003-media-storage.md`. `compose.s3.yaml` rehearses it from a
   laptop; Plan D step 4 performs it.

---

## 0. Before you run anything

### 0.1 Docker

On WSL2 or Linux, Docker Engine rather than Docker Desktop: it is what the
EC2 hosts will run, and Compose ships with it as a plugin. On macOS, Docker
Desktop is the only option and every command below is identical. Either
way, `docker compose version` must answer; if it does not, this section is
for you.

Engine from the official apt repository, not Ubuntu's `docker.io`, which
lags:

```bash
sudo apt update && sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

If `ps -p 1 -o comm=` says `systemd`, the daemon starts with the distro. If
it says `init`, either enable systemd (`[boot] systemd=true` in
`/etc/wsl.conf`, then `wsl --shutdown` from PowerShell) or add
`sudo service docker start` to the ritual `docs/TESTING.md` already has for
PostgreSQL. Then **open a new terminal** — group membership does not apply
to the shell that ran `usermod` — and confirm both halves answer:

```bash
id -nG | grep -o docker
docker version          # a Client section AND a Server section
```

### 0.2 The images

`server/Dockerfile` and `client/Dockerfile`, both verified alone before this
plan — see `plan-d-docker.md`. Compose builds them itself; nothing needs to
be built by hand first.

> The web image is the backend's stand-in. The frontend workstream owns
> `client/Dockerfile`; when theirs lands, `compose.yaml` changes by one line
> at most, provided it meets the contract in `plan-d-docker.md`.

### 0.3 Four files at the repository root

`compose.yaml`, `compose.ci.yaml`, `compose.s3.yaml`, `.env.example`. Check
their names with `ls -la`: two of them are dot-files, and a browser download
drops the leading dot. This bit the session twice (`dockerignore`,
`env.example`) — the Troubleshooting table has the symptoms.

---

## 1. Configure

```bash
cd <repo>
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # paste as SECRET_KEY
nano .env                                                         # SECRET_KEY, POSTGRES_PASSWORD, SEED_ADMIN_PASSWORD
export GIT_COMMIT=$(git rev-parse --short HEAD)
```

`.env` is read by `docker compose` to interpolate `compose.yaml`; it is not
handed to any container. `compose.yaml` names every variable each service
receives, so `docker compose config` is the complete answer to "what can this
container see". `server/.env`, the file `manage.py` reads for a laptop run,
is a different file and the images never see it.

`GIT_COMMIT` is exported, not written to `.env`, because it goes stale on
every commit. The cost is that **every new terminal needs the export again**.
Forget it and nothing fails: the images are tagged `:dev`, `/api/version/`
reports `dev`, and the smoke suite skips its commit check. The `dev` tag in
`docker compose ps` is the tell.

If you run `up` before `.env` exists, the stack refuses to start and lists
every missing variable by name. That is the `:?` guard in `compose.yaml`
doing its job — the same fail-fast the prod settings module applies, one
layer earlier, with a better message.

---

## 2. Run

```bash
docker compose up -d --build
```

The output is the dependency graph being walked:

```
Container rmit-store-db-1       Healthy
Container rmit-store-migrate-1  Exited
Container rmit-store-api-1      Healthy
Container rmit-store-web-1      Started
```

`web` reports `Started`, not `Healthy`: Compose only waits for the health of
a service something else depends on. `docker compose ps` shows it `(healthy)`
a few seconds later.

```bash
docker compose ps                       # db, api, web healthy; migrate Exited (0)
docker compose logs migrate | tail -3   # the migrations applied
curl -s localhost/api/version/          # {"version":"1.0.0","commit":"<sha>"}
curl -i localhost/readyz/ | head -1     # 200 — database and storage both ok
curl -s localhost/api/products/         # {"count":0, ... "results":[]}
```

The empty catalogue is the point of the last line: browser → nginx → gunicorn
→ PostgreSQL is connected end to end before any data exists.

---

## 3. Seed

```bash
docker compose --profile seed run --rm seed
```

The command reports what it created — 15 categories, 15 brands, 42 products,
the demo member and merchant with 5 more products, 160 reviews — and finishes
with the totals: 47 products, 160 reviews, 3 users. It takes a moment, and
the products land before the reviews do.

```bash
curl -s localhost/api/products/ | grep -o '"image_url":"[^"]*"' | head -1
# "image_url":"http://localhost/media/products/<hash>.jpg"
curl -sI http://localhost/media/products/<hash>.jpg | head -1
# HTTP/1.1 200 OK
```

That 200 is `web` serving a file `api` wrote: the shared volume, working.

Open `http://localhost` **after** the seed reports `Seeding complete`. A page
loaded while it is still running shows *Top rated* full of unreviewed hoodies,
because every product had a rating of zero at that instant and the ordering
fell through to primary key. Reload; the polos and the tote bag come back at
4.7 stars. Evidence: `docs/evidence/REQ-2-02-store-live-on-compose.png`.

---

## 4. Run again — the convergence check

```bash
docker compose up -d
```

`migrate` runs again and exits 0 with `No migrations to apply`; nothing else
is recreated. This is the Compose equivalent of Plan C's `changed=0`: the
command is safe to repeat, and a repeat proves the state is what the file
says. Running `seed` again is equally safe — it skips what already exists.

---

## 5. Verify

### 5.1 The smoke suite, from inside the stack

The same 23 checks Plans B and C ran from a laptop, now run from a container
on the compose network, with no laptop virtualenv involved:

```bash
mkdir -p server/test-reports
docker compose -f compose.yaml -f compose.ci.yaml run --rm \
    -e SMOKE_BASE_URL=http://web -e SMOKE_SPA_BASE_URL=http://web \
    -e SMOKE_EXPECTED_COMMIT=$GIT_COMMIT -e SMOKE_EXPECTED_VERSION=1.0.0 \
    -e SMOKE_MEMBER_EMAIL=member@rmit.edu.au -e SMOKE_MEMBER_PASSWORD='DemoPass2767!' \
    test pytest -m smoke --no-cov
```

`23 passed`. Two things make this work: `web` is one of the four names in the
API's `ALLOWED_HOSTS` (the others are the public host, `127.0.0.1` for the
readiness check, and `api` for anything that reaches gunicorn directly), and
`GIT_COMMIT` is exported in this terminal. Without the export the run reports
`21 passed, 2 skipped` and says why: `SMOKE_EXPECTED_COMMIT is not set`.
Evidence: `docs/evidence/REQ-5-05-smoke-green-in-stack.png`.

From a laptop virtualenv instead, the Plan C way, with `http://localhost` for
both base URLs — same 23.

### 5.2 Two API replicas behind one nginx

```bash
docker compose up -d --scale api=2
docker compose ps        # api-1 and api-2 both (healthy), one web
```

Reload the storefront: every image still loads. Docker's DNS returns both
addresses for `api` and the resolver in nginx spreads requests across them;
both replicas read the same volume, so an upload made through one is served
whichever one answers. `migrate` still ran once.

What this proves: the shared volume answers the "second replica breaks
images" problem **on one host**. What it does not prove: anything about two
hosts, where there is no shared disk. That is Plan D step 4 and S3.
Evidence: `docs/evidence/plan-e/two-api-replicas.png`.

### 5.3 The suite, the way CI will run it

```bash
mkdir -p server/test-reports
docker compose -f compose.yaml -f compose.ci.yaml run --rm test
```

Builds the `test` target, waits for `db`, runs `pytest --cov-fail-under=65`:
`322 passed`, `66.02%`, `junit.xml` and `coverage.xml` in
`server/test-reports/` for the Jenkins publishers. Same number as the laptop
and the Plan C instance, and now the same interpreter as production — the
`test` stage is layered on the runtime image's bytes. Evidence:
`docs/evidence/REQ-3-01-suite-green-in-ci-overlay.png`.

The `mkdir` is not decoration. A bind mount whose host directory does not
exist is created by the daemon as root, and the container runs as UID 1000;
the first run in a fresh Jenkins workspace would fail writing the reports.

---

## 6. Stop

```bash
docker compose down        # containers and network gone; pgdata and media kept
docker compose down -v     # ...and the volumes, for a genuinely fresh start
```

After a plain `down`, the next `up -d` comes back with the catalogue intact
and `migrate` reporting nothing to apply.

---

## 7. The S3 rehearsal

`compose.s3.yaml` passes the Learner Lab's session credentials from the
shell into `api` and `seed`, so the `USE_S3` switch can be exercised from a
laptop before any instance exists. It was run on 08/09 as the first step of
Plan D's two-instance session; `plan-d-docker.md` §4.3 is the full record,
including the stale-test-image trap it found.

```bash
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_SESSION_TOKEN=...
USE_S3=True AWS_STORAGE_BUCKET_NAME=<bucket> \
    docker compose -f compose.yaml -f compose.s3.yaml up -d --build
```

What it shows: `/readyz/` reporting `storage: ok` against the real bucket,
`seed` writing 47 objects, `image_url` pointing at S3, a browser loading it.
What it exposes early: the region, the bucket policy, and whether the
account allows a public-read bucket at all.

---

## Troubleshooting

Every row was hit during the session that produced this document.

### Files

| Symptom | Cause |
|---|---|
| `cp: cannot stat '.env.example'` | the download dropped the leading dot — `ls -la`, `mv env.example .env.example` |
| `load .dockerignore → transferring context: 2B` in a build log | same: Docker found no `.dockerignore` at the context root; a correct one reports its size in kB |
| `error while interpolating services.api.environment.SECRET_KEY: required variable ... is missing a value` — dozens of lines | no `.env`, or a placeholder left blank. Designed behaviour; fill the file |
| `$EDITOR .env` does nothing, or runs `.env` | `EDITOR` is unset — use `nano .env` |

### Docker

| Symptom | Cause |
|---|---|
| `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock` | the `docker` group has not applied to this shell — open a new terminal, or `newgrp docker` |
| `docker: invalid reference format` | a `$SHA`/`$GIT_COMMIT` that is empty in this terminal produced a tag with nothing after the colon |
| images tagged `:dev`; `/api/version/` reports `dev`; smoke run says `21 passed, 2 skipped` | `GIT_COMMIT` not exported in this terminal, so `.env`'s `dev` default applied — export and `up -d --build` |
| `docker image ls a b` → `requires at most 1 argument` | use `docker image ls --filter reference='rmit-store-*'` |
| `The command 'docker' could not be found in this WSL 2 distro` | Docker Engine not installed; the message's Docker Desktop advice is optional — 0.1 above |

### The stack

| Symptom | Cause |
|---|---|
| `web` says `Started`, not `Healthy`, in the `up` output | nothing depends on `web`, so Compose does not wait for it; `docker compose ps` shows `(healthy)` |
| `502 Bad Gateway` on every `/api/` path, `web` healthy | `api` is not up or not resolvable — `docker compose ps`, `docker compose logs api`. A 502 within five seconds is the web tier's `proxy_connect_timeout` doing what it should |
| `400 Bad Request` from the API, reached through `web` or scraped directly | the `Host` the request carried is not one of the four in `ALLOWED_HOSTS` — a new caller needs a new name in the list |
| admin login accepts the password and returns to the login page | `COOKIE_SECURE=True` on plain http — the secure cookie is never sent |
| *Top rated* shows hoodies with `No reviews yet` | the page loaded while `seed` was still running; reload |
| `Permission denied: '/app/test-reports/junit.xml'` from the test run | the bind-mount directory was created by the daemon as root — `mkdir -p server/test-reports` before the first run |
| `migrate` `Exited (1)` and `api` never starts | read `docker compose logs migrate`; the usual cause is a database variable, and `api` not starting is the correct outcome |

For the images themselves — default build target, bytecode caches, the
gunicorn control socket — see the table in `plan-d-docker.md`.

---

## What this tells us about the pipeline

- **The image is the unit of promotion, and Plan E already exercised it.**
  One `rmit-store-api:<sha>` ran `migrate`, `api`, `seed` and, layered, the
  test suite. Nothing was rebuilt between those roles. That is "build once,
  promote unchanged" before Jenkins exists.
- **Migration ordering is a pipeline stage, not an entrypoint.** Compose
  expresses it as `depends_on` conditions. Swarm ignores those conditions, so
  Plan F re-expresses the same rule as a Jenkins stage: run the migrate
  container, check its exit code, then update the service.
- **The two health questions map onto two mechanisms.** Liveness in the image
  becomes Swarm's restart trigger; readiness becomes the deploy gate and the
  target for the blue/green check via `/api/version/`.
- **`compose.ci.yaml` is the Jenkins test stage, verbatim.** `run --rm test`,
  publish `server/test-reports/`. The `mkdir` goes in the stage too.
- **One host is the ceiling for the volume.** `--scale api=2` worked because
  both replicas shared a disk. Two instances do not; S3 is not an
  enhancement but the precondition for the second host.
- **`.env` is the last time secrets live in a file.** Jenkins credentials and
  SSM take over in Plan F; `compose.yaml` already names every variable, so the
  hand-over is a list, not an audit.
