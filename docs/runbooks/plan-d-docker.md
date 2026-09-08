<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 08/09/2026
Last modified: 08/09/2026
Acknowledgement: Structure follows Plan D of UPSTREAM-README.md and the Plan C
runbook in this directory. Drafted with Claude (Anthropic) in guided sessions
from the terminal transcripts of 07/09 (the images) and 08/09 (two instances
with S3); the author performed every step, hit every row of the
troubleshooting tables, and verified the result.
-->

# Plan D — the RMIT Store as two images, on two instances, with S3

**Plan D is complete.** Tom's four steps — an image for the API, an image for
the frontend, a decision about `config.js`, and the containers running on
separate instances — were done and evidenced across two sessions. The
images were built and verified on 07/09; the two-instance run with uploads
on S3 was done on 08/09.

This runbook is written so that **any member of the team** can repeat it on
their own laptop and their own Learner Lab. Where a value is specific to the
08/09 session it is in the table in §4.0, and the commands use placeholders.
Angle-bracketed values like `<web-eip>` are placeholders. Substitute before
pasting; bash reads `<x>` as a file redirect, and that exact mistake cost two
pastes on 08/09.

> Plan E ran between D's third and fourth steps on purpose: Compose is the
> cheapest proof that two images work together, and every problem found there
> was a problem not found on an instance. Read `plan-e-compose.md` first if
> you have not run the stack locally.

---

## What you need, whoever you are

| | Linux / WSL2 | macOS | Notes |
|---|---|---|---|
| Docker | Docker Engine (`plan-e-compose.md` §0.1) | Docker Desktop | same commands either way |
| AWS CLI v2 | `sudo apt install awscli` | `brew install awscli` | Learner Lab session credentials pasted per session, §4.1 |
| SSH key pair | the `.pem` from your Learner Lab, on the Linux filesystem at mode 400 | same | never under `/mnt/c/` on WSL — Plan B §1 |
| git | yes | yes | the image tag is a commit |
| Python | only for the laptop smoke run in §4.8 — the container alternative needs none | | |

The repository can be cloned anywhere; `<repo>` below means that directory.
The two instances never see git, Python or Node: they receive images.

---

## What changes from Plan C

Plan C turned a process into a playbook. Plan D turns the playbook's result
into an artefact: instead of installing Python, cloning the repository,
building a virtualenv and running `collectstatic` on an instance, all of
that happens once, in a build, and the instance receives the finished thing.

| Plan C did this on the instance | Plan D does this in the image |
|---|---|
| install Python 3.11, create `.venv`, `pip install` | `python:3.14-slim`, dependencies in `/opt/venv`, copied into the runtime stage |
| clone the repository with a deploy key | five paths copied at build; the instance never sees git |
| `collectstatic` under prod settings | the same, as a build step — output identical on every replica |
| systemd unit binds gunicorn to `127.0.0.1:8000` behind nginx | gunicorn binds `0.0.0.0:8000`; the container network is the boundary |
| nginx on the API host serves `/static/` and `/media/` from disk | whitenoise serves `/static/` from the image; `/media/` is S3 |
| `manage.py migrate` as a play task | not in the image at all — a separate invocation of it |
| NodeSource 22 and a Vite build on the web instance | `node:22-alpine` build stage; the final image is nginx and `dist/`, no Node |
| uploads on the instance's disk | uploads in a bucket, credentials from the instance role |

Everything Plan C decided about *behaviour* — prod settings, `Host` header
forwarding, `/readyz/` as the readiness signal, no migrations from a service
entrypoint — carries over unchanged. What changed is *where* it lives.

---

## 1. The API image — `server/Dockerfile`

Three stages. `builder` resolves dependencies into a virtualenv; `runtime`
is what ships; `test` layers the suite and dev requirements on top of
`runtime`, so CI tests the exact bytes that deploy.

```bash
cd <repo>/server
SHA=$(git rev-parse --short HEAD)
docker build --target runtime -t rmit-store-api:$SHA --build-arg GIT_COMMIT=$SHA .
docker build --target test    -t rmit-store-api-test:$SHA .
```

**Always name the target.** With no `--target`, Docker builds the *last*
stage in the file, and that is `test`, because `test` must come after the
`runtime` it derives from. The first build on 07/09 found this the expensive
way: it failed inside `test` and tagged nothing.

### Decisions, and why

- **`python:3.14-slim`.** The interpreter the 345-test suite has been run
  on; Django 5.2.8+ supports it; pinning it here retires the laptop/instance
  drift (3.14 vs 3.11) that Plan C recorded. Patch level floats on purpose.
- **Explicit `COPY` of five paths, not `COPY . .`.** `manage.py`, `config`,
  `apps`, `templates`, `seed_assets`. Tests, dev requirements, the
  virtualenv and any `.env` are absent by construction; `docker run <image>
  ls` is the complete inventory.
- **`collectstatic` in the build, under prod settings.** Static files are a
  build artefact (`docs/adr/0003-media-storage.md`). Prod refuses to boot
  without `SECRET_KEY` and `ALLOWED_HOSTS`, so the build step passes
  throwaway values; nothing touches a database.
- **`DJANGO_SETTINGS_MODULE=config.settings.prod` baked as `ENV`.** A
  container started with no configuration fails at once with the
  `SECRET_KEY` guard rather than serving DEBUG pages.
- **No migrate anywhere in the image.** Decision on record since Plan C. The
  same image runs `manage.py migrate` as its own container (Plan E) or a
  separate `docker run` (§4.6) or a pipeline stage (Plan F).
- **UID 1000, non-root, numeric.** Numeric so an orchestrator's non-root
  check can verify it without `/etc/passwd`; 1000 so files written into a
  bind mount on a laptop come out owned by the developer.
- **`WEB_CONCURRENCY=3` as `ENV`.** gunicorn reads it natively for
  `--workers`; worker count is configuration with no entrypoint script.
- **`--forwarded-allow-ips '*'`.** The one change to the gunicorn command
  line from Plan C. There the proxy arrived from loopback, which gunicorn
  trusts by default; here it is another container, never loopback.
- **`--no-control-socket`.** gunicorn 25.1+ opens a management socket under
  `$HOME/.gunicorn/` by default; this user has no home, and every boot
  logged an ERROR before serving normally. Nothing runs `gunicornc` in a
  container.
- **`HEALTHCHECK` on `/healthz/`** — liveness. Compose overrides it with
  `/readyz/`, which is readiness; `plan-e-compose.md` explains which
  mechanism asks which.
- **`test` stage resets `DJANGO_SETTINGS_MODULE` to `test`.** pytest-django
  gives the environment variable precedence over `pytest.ini`; inheriting
  `prod` would kill the suite on the guard before collecting a test.

### Verify — without a database

```bash
docker image ls --filter reference='rmit-store-api*'          # runtime ≈130 MB content, test ≈137 MB
docker run --rm rmit-store-api:$SHA ls                       # apps config manage.py media seed_assets staticfiles templates
docker run --rm rmit-store-api:$SHA find . -name __pycache__ # nothing
docker run --rm rmit-store-api:$SHA id                       # uid=1000(app)
docker run --rm rmit-store-api-test:$SHA ls tests            # conftest.py integration smoke unit ...
docker run --rm rmit-store-api:$SHA; echo "exit $?"          # RuntimeError: SECRET_KEY ..., exit 1

docker run -d --name api-verify -p 8000:8000 \
    -e SECRET_KEY=verify-only -e ALLOWED_HOSTS=localhost,127.0.0.1 rmit-store-api:$SHA
sleep 3
curl -i localhost:8000/healthz/ | head -1                    # 200
curl -i localhost:8000/readyz/  | head -1                    # 503 — {"database":"unavailable","storage":"ok"}
curl -s localhost:8000/api/version/                          # {"version":"1.0.0","commit":"<sha>"}
curl -sI localhost:8000/static/admin/css/base.css | head -1  # 200 — collectstatic ran in the build
sleep 30; docker ps --format '{{.Names}} {{.Status}}'        # api-verify ... (healthy)
docker logs api-verify                                       # three workers, no ERROR line
docker rm -f api-verify
```

`(healthy)` beside a 503 from `/readyz/` is the liveness/readiness
distinction in one line, and something Plan C could never show: a healthy
process with no database is not a process to restart.

### Verify — the suite inside the image

```bash
docker network create verify
docker run -d --name db --network verify \
    -e POSTGRES_USER=rmit -e POSTGRES_PASSWORD=rmit -e POSTGRES_DB=rmit_store postgres:16-alpine
until docker exec db pg_isready -U rmit -d rmit_store; do sleep 1; done
docker run --rm --network verify -e DATABASE_URL=postgres://rmit:rmit@db:5432/rmit_store \
    -v "$PWD/test-reports:/app/test-reports" rmit-store-api-test:$SHA
docker rm -f db && docker network rm verify
```

`322 passed`, `66.02%`, on Python 3.14.7 with `settings: config.settings.test
(from env)` confirming the override. This is what `compose.ci.yaml` encodes;
doing it by hand once is Tom's own rule applied to CI.

---

## 2. The web image — `client/Dockerfile`

> **Ownership.** The frontend workstream owns this image. The version in the
> backend branch is a working stand-in so Plans D and E could run, offered to
> them as a starting point. Whoever owns it, the image must meet the contract
> at the end of this section, or neither Compose nor §4 works.

Two stages: `node:22-alpine` runs `npm ci` and `vite build`;
`nginx:1.30-alpine` ships `dist/` and a site configuration. No Node in the
final image — Tom's hard requirement.

```bash
cd <repo>/client
docker build -t rmit-store-web:$SHA --build-arg GIT_COMMIT=$SHA .
```

### Decisions, and why

- **`npm ci`, not `npm install`,** and `NODE_ENV` deliberately not set to
  `production` before it: vite, the Vue plugin and sass are devDependencies
  and would be skipped. Vite picks production mode for `build` on its own.
- **The site configuration is a template rendered at start.** The nginx
  image's entrypoint substitutes `${API_UPSTREAM}` into
  `/etc/nginx/conf.d/default.conf` before nginx starts. One image serves
  `api:8000` under Compose and a private IP on two instances.
- **The upstream is resolved per request** via `resolver 127.0.0.11` and a
  variable in `proxy_pass`, because container addresses move and an
  `upstream` block resolves once. With an IP literal the resolver is idle.
- **`/static/` is proxied**, not served — the files are in the API image.
- **`/media/` is an `alias` to `/srv/media/`**, a mount point: the shared
  volume under Compose, nothing (404) under S3, where `image_url` never
  points here anyway.
- **IPv4 only.** The `[::]:80` listener from Plan C is gone: Docker publishes
  over IPv4, and the listener makes nginx refuse to start on a host with
  IPv6 disabled.
- **`config.js` is baked with `/api` and remains mountable.** Tom's step 3:
  the relative path is correct everywhere because this nginx proxies
  `/api/` itself; a different file mounted over
  `/usr/share/nginx/html/config.js` needs no rebuild.
- **`HEALTHCHECK` on `/`** — nginx's own liveness. A web tier whose API is
  down should be alive and returning 502 at the edge, not restarting.

### Verify — alone

```bash
docker run --rm rmit-store-web:$SHA sh -c 'which node npm; echo "exit $?"'   # exit 1: no Node shipped
docker run --rm rmit-store-web:$SHA ls /usr/share/nginx/html                  # assets config.js images index.html
docker run -d --name web-verify -p 8080:80 rmit-store-web:$SHA
docker exec web-verify grep rmit_api /etc/nginx/conf.d/default.conf   # set $rmit_api http://api:8000;
curl -sI localhost:8080/ | head -1                                    # 200
curl -sI localhost:8080/shop | head -1                                # 200 — SPA fallback
curl -sI localhost:8080/config.js | grep -i cache-control             # no-store
curl -sI localhost:8080/api/products/ | head -1                       # 502 in ~5 s: nothing at api:8000
docker ps --format '{{.Names}} {{.Status}}'                           # (healthy) with the API absent
docker rm -f web-verify
```

The 502 is the desired result: the web tier alive and reporting the API's
absence, which is what a health-based deploy gate needs to see.

### The contract

Whatever `client/Dockerfile` finally lands, the image must:

1. proxy `/api/`, `/admin/`, `/healthz/`, `/readyz/` and `/static/` to the
   API, forwarding `Host $host` unchanged;
2. take the API address at run time (`API_UPSTREAM` or equivalent), not at
   build time;
3. fall back to `index.html` for unknown paths; serve `config.js` with
   `Cache-Control: no-store`; serve `/media/` from a mount point;
4. listen on 80, ship no Node, and answer its healthcheck with the API down.

---

## 3. `config.js` at run time

Decided above and recorded here because Tom lists it as its own step: the
built `dist/config.js` carries `API_BASE_URL: '/api'`, correct in every
environment because the web tier proxies `/api/`. The runtime mechanism
(mount a file over it) is retained and needs no code; no plan so far has
needed it, and that is the point — nothing has needed a rebuild per
environment.

---

## 4. Two instances, uploads on S3

### 4.0 What the 08/09 session used

Reuse these to bring the same deployment back, or create your own and
substitute. Nothing below is a secret.

| Placeholder | 08/09 value |
|---|---|
| `<account>` | `115972158049` |
| `<region>` | `us-east-1` (the only Learner Lab region; `.env.example`'s `ap-southeast-2` default is wrong here) |
| `<bucket>` | `rmit-store-media-t15-260908` |
| `<sha>` | `d93338b` — the images in ECR carry this tag |
| web instance | `i-037f909dc9ff595f3`, `t3.small`, AL2023, Elastic IP `<web-eip>` = `50.16.88.48`, private `172.31.24.216` |
| api instance | `i-0c6167bfa6bcbd4b8`, `t3.small`, AL2023, private `<api-private-ip>` = `172.31.28.167`; its public address changes on every start and nothing uses it |
| `web-sg-plan-d` | inbound 80 and 22 from `0.0.0.0/0` |
| `api-sg-plan-d` | inbound **8000** and 22 from `web-sg-plan-d` only — no rule from the internet |
| both instances | `LabInstanceProfile`, IMDSv2 required, **metadata hop limit 2**, Docker 25.0.16 from `dnf` |

Why new instances rather than the Plan C pair: that pair is converged and
evidenced, and turning it into Docker hosts would mean unpicking
Ansible-managed state by hand — the opposite of the lesson. New instances
need Docker, a profile and a group rule, nothing else.

Why S3 now rather than in Plan F: two hosts have no shared disk. Upstream
already supports the switch (`USE_S3`, no code change); the ADR's trigger
moved from Plan F to here.

### 4.1 Laptop: credentials, then the instance check

Learner Lab page → *AWS Details* → *AWS CLI: Show* → paste the `[default]`
block:

```bash
mkdir -p ~/.aws && chmod 700 ~/.aws
nano ~/.aws/credentials                 # the three-line block, exactly as shown
printf '[default]\nregion = us-east-1\noutput = json\n' > ~/.aws/config
chmod 600 ~/.aws/credentials
aws sts get-caller-identity             # your account id
```

**These expire with the lab session.** A command that worked a minute ago
failing with `explicit deny ... policy/voc-cancel-cred` is the session
having rotated them; re-paste, it is not a permissions problem. It happened
between two consecutive commands on 08/09.

With the instances launched (console: *Advanced details* → IAM instance
profile `LabInstanceProfile`, metadata V2 only, hop limit 2), verify the two
things the console summary does not show:

```bash
aws ec2 describe-instances --instance-ids <web-instance-id> <api-instance-id> \
    --query 'Reservations[].Instances[].[Tags[?Key==`Name`].Value|[0],MetadataOptions.HttpTokens,MetadataOptions.HttpPutResponseHopLimit,IamInstanceProfile.Arn]' --output table
# required | 2 | ...instance-profile/LabInstanceProfile   on both rows
```

Hop limit 1 is the trap this exists for: a process in a bridge-networked
container is one hop further from `169.254.169.254` than a process on the
host, and with the limit at 1 credentials never arrive — the error names S3,
not IMDS. Fix on a running instance:
`aws ec2 modify-instance-metadata-options --instance-id <id> --http-put-response-hop-limit 2 --http-endpoint enabled`.

### 4.2 Laptop: the bucket

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET=rmit-store-media-t15-$(date +%y%m%d)          # globally unique; or your own name
aws s3api create-bucket --bucket $BUCKET --region us-east-1     # no LocationConstraint in us-east-1
aws s3api put-public-access-block --bucket $BUCKET --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false
aws s3api put-bucket-policy --bucket $BUCKET --policy "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"PublicReadMedia\",\"Effect\":\"Allow\",\"Principal\":\"*\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::$BUCKET/media/*\"}]}"
echo probe > /tmp/probe.txt && aws s3 cp /tmp/probe.txt s3://$BUCKET/media/probe.txt
curl -sI https://$BUCKET.s3.amazonaws.com/media/probe.txt | head -1     # 200 — public read works
echo $BUCKET                                                            # write it down
```

The `put-*` calls print nothing on success. `AccessDenied` on
`put-bucket-policy` would mean the account forbids public buckets; the
fallback is `AWS_S3_QUERYSTRING_AUTH=True` (presigned URLs, no policy) in
`api.env` — one variable. Not needed on 08/09. Evidence:
`docs/evidence/plan-d/bucket-policy-probe.png`.

### 4.3 Laptop: rehearse the S3 switch on Compose

Proves the bucket, the region and the upload path before any instance is
involved, with the session credentials from the shell — never from a file:

```bash
cd <repo>
export GIT_COMMIT=$(git rev-parse --short HEAD) BUCKET=<bucket>
eval "$(aws configure export-credentials --format env)"   # AWS_ACCESS_KEY_ID / SECRET / SESSION_TOKEN from ~/.aws
export USE_S3=True AWS_STORAGE_BUCKET_NAME=$BUCKET
docker compose down -v                                    # empty DB, so seed uploads rather than skips
docker compose -f compose.yaml -f compose.s3.yaml up -d --build
sleep 5; curl -s localhost/readyz/; echo                  # {"database":"ok","storage":"ok"}
docker compose -f compose.yaml -f compose.s3.yaml --profile seed run --rm seed
curl -s localhost/api/products/ | grep -o '"image_url":"[^"]*"' | head -1   # https://<bucket>.s3.amazonaws.com/media/products/...
aws s3 ls s3://$BUCKET/media/products/ | wc -l            # 47
```

Wait for the prompt after `seed` before pasting anything else: `compose run`
attaches your terminal to the container, and commands pasted while it runs
go to the container, not to bash. On 08/09 the next five commands vanished
that way.

Then the smoke suite, with the test image **rebuilt** so it carries the
S3-aware media test (`test_product_image_urls_are_absolute_and_load`, which
fetches the URL instead of asserting its host):

```bash
docker compose -f compose.yaml -f compose.ci.yaml build test
docker compose -f compose.yaml -f compose.ci.yaml run --rm \
    -e SMOKE_BASE_URL=http://web -e SMOKE_SPA_BASE_URL=http://web -e SMOKE_EXPECTED_COMMIT=$GIT_COMMIT \
    -e SMOKE_EXPECTED_VERSION=1.0.0 -e SMOKE_MEMBER_EMAIL=member@rmit.edu.au -e SMOKE_MEMBER_PASSWORD='DemoPass2767!' \
    test pytest -m smoke --no-cov                          # 23 passed
```

Without the `build`, the stale test image ran the Plan C assertion and
failed on the S3 URL — correctly, for the old test — which is what the
rewrite was for. Open `http://localhost` with DevTools → Network → *Images*:
the product photographs come from the bucket. Evidence:
`docs/evidence/plan-d/s3-rehearsal-readyz-and-image-url.png` and
`s3-rehearsal-storefront-images-from-s3.png`.

Tear down and empty the bucket, so the count in §4.8 is the instance's:

```bash
docker compose down -v
unset USE_S3 AWS_STORAGE_BUCKET_NAME AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
aws s3 rm s3://$BUCKET/media/products/ --recursive
```

### 4.4 Laptop: push the images to ECR

```bash
aws ecr create-repository --repository-name rmit-store-api
aws ecr create-repository --repository-name rmit-store-web
ECR=$ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR
docker tag rmit-store-api:$GIT_COMMIT $ECR/rmit-store-api:$GIT_COMMIT && docker push $ECR/rmit-store-api:$GIT_COMMIT
docker tag rmit-store-web:$GIT_COMMIT $ECR/rmit-store-web:$GIT_COMMIT && docker push $ECR/rmit-store-web:$GIT_COMMIT
echo "ECR=$ECR  TAG=$GIT_COMMIT  BUCKET=$BUCKET"          # the three values the instance shells need
```

ECR because it is AWS (REQ-1), the instance profile pulls from it with no
credentials, and pushing is HTTPS — campus wifi is not involved. Evidence:
`docs/evidence/plan-d/ecr-push.png`.

### 4.5 Laptop: the env files, then over the wire

The instances never clone the repository, so the files are filled on the
laptop and copied. Templates in `deploy/plan-d/`; the filled files are
ignored by git (`*.env` in `.gitignore`) — check that rule exists before
you fill anything, and check `git status` after.

```bash
cd <repo>/deploy/plan-d
cp api.env.example api.env && cp db.env.example db.env && cp web.env.example web.env
SK=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
DBPW=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SK|" api.env
sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgres://rmit:$DBPW@db:5432/rmit_store|" api.env
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$DBPW|" db.env
nano api.env     # ALLOWED_HOSTS=<web-eip>,<api-private-ip>,127.0.0.1,localhost ; the three http://<web-eip> lines ; AWS_STORAGE_BUCKET_NAME=<bucket>
nano web.env     # API_UPSTREAM=<api-private-ip>:8000
grep -n "^SECRET_KEY=\|^DATABASE_URL=\|^POSTGRES_PASSWORD=\|^ALLOWED_HOSTS=\|^AWS_STORAGE_BUCKET_NAME=\|^API_UPSTREAM=" api.env db.env web.env
git status       # nothing under deploy/plan-d/
```

There is nothing to "remember": these are new values for new instances,
generated here, and their only home is the instance. `token_urlsafe` is
used for both because the password sits inside a URL and must contain no
`@`, `:`, `/`, `#` or space — `DB password` with a space was the 08/09
placeholder that would have broken both psql and the URL. If you ever need
the DB password later, it is in `~/db.env` on the API instance.

SSH goes through the web instance, because `api-sg-plan-d` accepts 22 only
from the web group. A bare `ssh -J` does not carry `-i` to the jump hop, so
put both hosts in `~/.ssh/config` once (the same pattern as Plan C §0.5):

```
Host web-plan-d
    HostName <web-eip>
    User ec2-user
    IdentityFile ~/.ssh/<key>.pem

Host api-plan-d
    HostName <api-private-ip>
    User ec2-user
    IdentityFile ~/.ssh/<key>.pem
    ProxyJump web-plan-d
```

```bash
scp web.env web-plan-d:~/
scp api.env db.env api-plan-d:~/
cd <repo>
```

If your SSH config lives on the Windows side (VS Code Remote-SSH reads
`C:\Users\<you>\.ssh\config`), copy the three files to a Windows folder,
`scp` from PowerShell, then delete that copy — they hold real secrets now.

### 4.6 API instance

`ssh api-plan-d` (or VS Code Remote-SSH). Docker was installed by hand with
`sudo dnf install -y docker && sudo systemctl enable --now docker && sudo usermod -aG docker ec2-user`;
Plan F automates that. The group applies to a **new** login — VS Code's
remote server keeps the old session, so either reconnect it or run
`newgrp docker` **alone, then** paste the rest; pasted as the first line of
a block, `newgrp` starts a new shell and discards everything after it.

Type the values, then run each block and wait for the prompt:

```bash
ECR=<account>.dkr.ecr.us-east-1.amazonaws.com
TAG=<sha>
id -nG | grep -o docker && docker version --format '{{.Server.Version}}'   # docker, 25.0.16
grep -c REPLACE ~/api.env ~/db.env                                         # 0 and 0
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR
docker pull $ECR/rmit-store-api:$TAG
```

The login succeeded with no keys on the instance: that is the profile. (The
"stored unencrypted" warning refers to a 12-hour ECR token; ignore it.)

```bash
docker network create store
docker run -d --name db --restart unless-stopped --network store --env-file db.env \
    -v pgdata:/var/lib/postgresql/data postgres:16-alpine
until docker exec db pg_isready -U rmit -d rmit_store; do sleep 1; done
```

```bash
docker run --rm --network store --env-file api.env $ECR/rmit-store-api:$TAG python manage.py migrate --noinput
```

```bash
docker run -d --name api --restart unless-stopped --network store --env-file api.env -p 8000:8000 $ECR/rmit-store-api:$TAG
sleep 5; curl -s 127.0.0.1:8000/readyz/; echo            # {"database":"ok","storage":"ok"}
```

Same order as Compose — database, migrate, api, seed — enforced by you
instead of `depends_on`. Nothing on this host publishes 5432.

```bash
read -s -p "admin password: " ADMIN_PW; echo             # keeps it out of the shell history
docker run --rm --network store --env-file api.env $ECR/rmit-store-api:$TAG \
    python manage.py seed_demo --demo-users --admin-email admin@rmit.edu.au --admin-password "$ADMIN_PW"
docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'  # db healthy, api (healthy) 0.0.0.0:8000
```

The line to look for in the seed output is
`INFO botocore.credentials Found credentials from IAM Role: LabRole`: a
container on the instance getting S3 credentials through the metadata
service, hop limit 2 working, no key anywhere. Evidence:
`docs/evidence/plan-d/api-instance-readyz-storage-ok.png`.

**What went wrong here on 08/09, and matters.** The first seed died with
`NoSuchBucket` although `/readyz/` had just reported `storage: ok`. The
bucket name in `api.env` was wrong — and the readiness probe cannot see
that: its storage check is `exists()`, a HEAD request, and S3 answers a
nonexistent bucket with a 404 that django-storages maps to "no such object"
without raising. So `readyz` proves credentials and reachability, and the
first write proves the name. Two consequences: `aws s3 ls s3://<bucket>` is
the real pre-check, and a half-seeded database was reset rather than
trusted (`docker rm -f db && docker volume rm pgdata`, then db → migrate →
seed again). Fixing the env file also needs `docker rm -f api` and a new
`docker run` — `docker restart` does not re-read `--env-file`.

### 4.7 Web instance

```bash
ECR=<account>.dkr.ecr.us-east-1.amazonaws.com
TAG=<sha>
grep -c REPLACE ~/web.env                                 # 0
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR
docker run -d --name web --restart unless-stopped --env-file web.env -p 80:80 $ECR/rmit-store-web:$TAG
sleep 3; curl -s localhost/api/version/; echo             # {"version":"1.0.0","commit":"<sha>"}
```

That line is nginx in the web container proxying to gunicorn in the API
container across the private network through the 8000 rule. A 502 instead
is `web.env`'s address or that rule.

### 4.8 Laptop: verify as a user would

```bash
cd <repo>
export GIT_COMMIT=<sha> BUCKET=<bucket> WEB=http://<web-eip>
curl -s $WEB/api/version/; echo
curl -s $WEB/readyz/; echo
curl -s $WEB/api/products/ | grep -o '"image_url":"[^"]*"' | head -1   # an S3 URL
aws s3 ls s3://$BUCKET/media/products/ | wc -l                          # 47 — all uploaded from the instance
```

The smoke suite against the Elastic IP, either way:

```bash
# from a laptop virtualenv (docs/TESTING.md)
cd server && source .venv/bin/activate
SMOKE_BASE_URL=$WEB SMOKE_SPA_BASE_URL=$WEB SMOKE_EXPECTED_COMMIT=$GIT_COMMIT SMOKE_EXPECTED_VERSION=1.0.0 \
    SMOKE_MEMBER_EMAIL=member@rmit.edu.au SMOKE_MEMBER_PASSWORD='DemoPass2767!' pytest -m smoke --no-cov
deactivate; cd ..

# or from the test container, no Python on the laptop at all
docker compose -f compose.yaml -f compose.ci.yaml run --rm --no-deps \
    -e SMOKE_BASE_URL=$WEB -e SMOKE_SPA_BASE_URL=$WEB -e SMOKE_EXPECTED_COMMIT=$GIT_COMMIT -e SMOKE_EXPECTED_VERSION=1.0.0 \
    -e SMOKE_MEMBER_EMAIL=member@rmit.edu.au -e SMOKE_MEMBER_PASSWORD='DemoPass2767!' \
    test pytest -m smoke --no-cov
```

`23 passed` on 08/09. Evidence: `docs/evidence/plan-d/smoke-23-against-eip.png`.

Then the browser at `http://<web-eip>` with DevTools → Network → *Images*.
The product photographs list a domain starting `<bucket>.s3.a…` with a lock
icon — the bucket name comes *before* `s3.amazonaws.com`, and the column
truncates it, which is why it looks at first as if nothing goes to S3. Widen
the column or click a row: `Server: AmazonS3` for the products,
`Server: nginx/1.30.4` for the logo, on the same page. Evidence:
`docs/evidence/REQ-2-03-two-instances-with-s3.png` — the decisive capture
for REQ-2's media question.

### 4.9 After a Learner Lab session ends

Both instances stop. Nothing is lost: the database is in the `pgdata`
volume on the API host, uploads are in the bucket, and every container was
started with `--restart unless-stopped`. On the next session: start the lab,
start both instances, wait a minute, and `curl http://<web-eip>/readyz/`.
The API's public address changes; the Elastic IP and both private addresses
do not, and those are the only ones in any env file. Re-paste CLI
credentials on the laptop as in §4.1.

---

## Troubleshooting

Every row in the first three tables was hit on 07/09 or 08/09.

### Building

| Symptom | Cause |
|---|---|
| `docker build .` with no `--target` fails inside `[test 2/5]` and tags nothing | the default target is the last stage, and that is `test` — name the target, always |
| `Could not open requirements file: '/app/requirements.txt'` in the `test` stage | `requirements-dev.txt` begins with `-r requirements.txt` and the runtime stage does not carry it — the `test` stage copies both |
| `find . -name __pycache__` lists every package after "fixing" `.dockerignore` | patterns anchor at the context root, unlike `.gitignore` — `**/__pycache__/` |
| the same, and the build log says `load .dockerignore → transferring context: 2B` | no `.dockerignore` at the context root: the download dropped the dot (`dockerignore`). Same for `env.example` and `.env.example` |
| `docker: invalid reference format` | `$SHA` / `$GIT_COMMIT` empty in this terminal → a tag with nothing after the colon. Export per terminal |
| images tagged `:dev`, `/api/version/` reports `dev`, smoke skips the commit check | same cause — `GIT_COMMIT` unset, so `.env`'s default applied |
| the smoke suite fails the media test on an S3 URL with the Plan C message | the test image is stale: `run` does not rebuild. `compose ... build test` |

### Running on a laptop

| Symptom | Cause |
|---|---|
| `[ERROR] Control server error: Permission denied: '/home/app'` on every gunicorn start | gunicorn ≥ 25.1 control socket; this user has no home — `--no-control-socket` |
| `nginx: [emerg] socket() [::]:80 failed (97: Address family not supported)` | IPv6 disabled on the host — the listener is removed from the template |
| commands pasted after `compose run` never execute, and appear inside the container's output | they went to the container's stdin. Wait for the prompt |
| `[200~` in front of a command, `command not found` | a bracketed-paste artefact from pasting into a prompt that was not ready; retype the first line |

### AWS and the instances

| Symptom | Cause |
|---|---|
| `explicit deny in an identity-based policy: ...policy/voc-cancel-cred` on something that just worked | the lab session rotated its credentials; re-paste them (§4.1) |
| `Command 'aws' not found` | AWS CLI not installed on the laptop: `sudo apt install awscli` / `brew install awscli` |
| `Unable to locate credentials` | `~/.aws/credentials` missing; the block from the lab page goes there |
| `bash: syntax error near unexpected token ';'` after `ECR=<same>` | a placeholder pasted literally; `<…>` is a redirect to bash |
| `docker login` goes to `registry-1.docker.io` and fails | `$ECR` was empty (previous row) |
| `ssh ec2-user@<api-public-dns>` times out | by design: `api-sg-plan-d` accepts 22 only from the web group. `ssh api-plan-d` via the config's ProxyJump |
| `Permission denied (publickey)` on the jump hop with `ssh -i key -J …` | `-i` is not passed to the jump; put `IdentityFile` in `~/.ssh/config` for both hosts |
| everything pasted after `newgrp docker` is echoed and nothing runs | `newgrp` starts a new shell and discards pending input. Run it alone |
| `permission denied ... docker.sock` in a VS Code remote terminal after `usermod` | the VS Code server predates the group change — reconnect it, or `newgrp docker` |
| `/readyz/` says `storage: ok` but seed raises `NoSuchBucket` | wrong `AWS_STORAGE_BUCKET_NAME` in `api.env`; the HEAD-based probe cannot see it. Fix the file, `docker rm -f api`, run again |
| `docker restart api` after editing `api.env` changes nothing | the environment is fixed at `docker run`; recreate the container |
| a partial seed (admin and categories created, products not) | reset: `docker rm -f db && docker volume rm pgdata`, then db → migrate → api → seed |
| `NoCredentialProviders` or S3 credential errors inside a container while `aws` on the host works | IMDS hop limit 1 — §4.1 |
| `502` from the web instance on `/api/` | `API_UPSTREAM` in `web.env`, or the 8000 rule on `api-sg-plan-d` |
| `400 Bad Request` from the API through the web host | the Elastic IP is not in `ALLOWED_HOSTS` in `api.env` |
| the DevTools Network tab seems to show no request to `s3.amazonaws.com` | the bucket name is a prefix of that domain and the column is truncated; widen it |

### Findings for Known Problems

- **The readiness probe is blind to a wrong bucket name.** `exists()` on a
  nonexistent bucket returns False rather than raising, so `/readyz/`
  reports storage ok until the first write. Upstream's `apps/core/health.py`;
  a write-probe would fix it and is a Plan F candidate.
- **The seed photographs are WebP files with `.jpg` names** (upstream
  `seed_assets/`); browsers sniff the real format, so nothing breaks, but
  the DevTools *Type* column says `webp` and a strict CDN might not.

---

## What this tells us about the pipeline

- **The image is the artefact; the instance is a place to run it.** Plan C's
  roles installed runtimes and built things on instances. In Plan F the
  only thing Ansible installs is Docker, and the only thing the pipeline
  ships is an image tagged with a commit — one image ran `migrate`, `api`
  and `seed` on the instance, unchanged from the one Compose and the test
  suite used.
- **Build on the agent, never on the instance.** The web build that ran a
  t3.small out of memory in Plan B is now a build stage; the instance
  received 20 MB of nginx and static files.
- **Tests run against the deployable bytes.** The `test` target is
  `FROM runtime`; there is no version of the code that CI tested and
  production did not receive.
- **Credentials come from the platform.** ECR pull and S3 write on the
  instances used the instance role through IMDSv2; the only keys typed all
  day were the laptop's session credentials, which expire. Jenkins in Plan F
  runs on an instance and inherits the same arrangement.
- **§4.6 and §4.7 are the Plan F playbook and pipeline, written out by
  hand.** Every `docker run` there becomes a task or a stage: install Docker
  (Ansible), login and pull (stage), migrate (stage, exit code checked),
  update the service (Swarm), `readyz` and `/api/version/` (gate). The
  order was performed by hand once, which is Tom's rule.
- **`API_UPSTREAM` and `USE_S3` are the two switches that make one image
  serve every plan.** Neither required touching upstream code; the
  modifications table in `docs/UPSTREAM.md` is still empty.
