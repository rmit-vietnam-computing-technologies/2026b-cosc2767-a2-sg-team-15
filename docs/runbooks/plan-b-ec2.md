<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 03/09/2026
Last modified: 03/09/2026
Acknowledgement: Structure follows Plan B of UPSTREAM-README.md.
Drafted with Claude (Anthropic) in a guided session; the author
performed the deployment and verified each step.
-->

# Plan B — deploy the RMIT Store on one EC2 instance

**This is the manual baseline.** Every step below is a step the pipeline
should eventually remove — that is the point of doing it by hand first.

> Times are from a real run: about 35 minutes end to end on a `t3.small`,
> excluding the false starts recorded in Troubleshooting.

---

## 0. Before you touch the instance

### 0.1 Elastic IP

EC2 → **Elastic IPs** → Allocate → Associate with the instance.

An Elastic IP survives a stop/start. It does **not** survive replacing the
instance — re-associating the same allocation to a new instance is what keeps
the address, and if you allocate a fresh one you are back to editing four
variables. This happened once during the session that produced this document.

### 0.2 Launch

| Setting | Value |
|---|---|
| AMI | Amazon Linux 2023 |
| Type | `t3.small` |
| Key pair | the lab-provided pair, or your own |
| Inbound | `22` from My IP, `80` from Anywhere |

`t3.micro` works but has 1 GB of RAM and the frontend build will be
OOM-killed — see 1.2. Nothing else needs opening: ports 8000 and 5173 never
face the internet in this plan, so there is no step later that closes them.

**Port 22 is scoped to My IP**, which is the network you launched from.
Move between home and campus and SSH will hang until you re-detect it in the
security group. A hang is the signature; every other SSH failure is fast.

### 0.3 SSH

The private key must live on the Linux filesystem. A `.pem` under `/mnt/c/`
cannot hold Unix permissions, `chmod 400` silently does not stick, and SSH
refuses to use a world-readable key.

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cp /mnt/c/Users/<you>/Downloads/<key>.pem ~/.ssh/
chmod 400 ~/.ssh/<key>.pem
```

Add a host entry so the address lives in one place:

```
Host rmit-ec2
  HostName ec2-<dashed-elastic-ip>.compute-1.amazonaws.com
  User ec2-user
  IdentityFile ~/.ssh/<key>.pem
  ForwardAgent yes
```

`ForwardAgent yes` lets the instance clone the repository using *your* key,
so no credential is ever written to its disk. It needs an agent running on
your machine, which WSL does not start by default:

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
ssh-add -l                      # must list the key
```

> VS Code's Remote-SSH runs as a Windows process and reads
> `C:\Users\<you>\.ssh\config`, not the WSL one. If you use it, the host
> entry and the key must be duplicated on the Windows side, with an absolute
> `IdentityFile` path. Agent forwarding will not carry over.

---

## 1. Prepare the instance

```bash
ssh rmit-ec2
whoami          # ec2-user — never root
```

Stay `ec2-user` throughout. nginx serves uploaded media out of this user's
home directory; a checkout owned by root cannot be traversed into no matter
how it is chmod'ed, and the symptom is a 403 on every product image with
nothing obviously wrong to find.

### 1.1 Swap

Skip on `t3.small` if you like. Mandatory on `t3.micro`.

```bash
sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
free -h
```

### 1.2 Runtimes

```bash
sudo dnf update -y
sudo dnf install -y git python3.11 python3.11-pip nginx \
                    postgresql16 postgresql16-server

curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo bash -
sudo dnf install -y nodejs

python3.11 --version && node --version
```

Amazon Linux 2023 ships Python **3.11**. Development is on 3.14, and the
container base in Plan F has to settle which one wins. Recorded in Known
Problems until it is.

### 1.3 PostgreSQL

```bash
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql nginx

sudo -u postgres psql -c "CREATE ROLE rmit LOGIN PASSWORD 'rmit' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE rmit_store OWNER rmit;"
```

A fresh `initdb` on Red Hat family systems writes `ident` authentication for
TCP connections. Django connects over TCP with a username and password, so it
is refused with `FATAL: Ident authentication failed`. Switch the `host` lines
and reload — the `local ... peer` lines are left alone, because that is what
`sudo -u postgres psql` uses:

```bash
sudo sed -i 's/^\(host.*\)ident$/\1scram-sha-256/' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl reload postgresql
```

**Gate.** Do not continue until this works:

```bash
PGPASSWORD=rmit psql -h 127.0.0.1 -U rmit -d rmit_store -c "SELECT 1;"
```

---

## 2. Code

```bash
ssh -T git@github.com           # greets you by username if forwarding works
cd ~
git clone git@github.com:<org>/2026b-cosc2767-a2-sg-team-15.git
cd 2026b-cosc2767-a2-sg-team-15/server
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The virtualenv must be at **`server/.venv`**. `rmit-api.service` hard-codes
that path, and a venv one level up produces `status=203/EXEC` from systemd —
an error that says nothing about paths. Keeping it here also matches the
laptop layout in `docs/TESTING.md`, so one set of instructions works in both
places.

`requirements.txt`, not `requirements-dev.txt`: the deployment does not run
tests. The smoke suite runs from a laptop or a build agent, against this
instance over HTTP.

> If agent forwarding is unavailable — a Remote-SSH session, or a laptop that
> disconnects — generate a key on the instance and register its public half
> as a **read-only deploy key** on the repository instead:
> `ssh-keygen -t ed25519 -C "rmit-store-plan-b" -f ~/.ssh/id_ed25519 -N ""`

---

## 3. Configuration

Secrets go to `/etc`, root-owned, mode 600 — **not** into a `.env` inside the
checkout. Serving media requires `chmod o+x /home/ec2-user` (step 5.2), which
makes that directory traversable by every local account. Keeping the same
twelve-factor shape while putting the file where permissions actually mean
something costs nothing, and it is the same idea as `--env-file` once this
becomes a container.

```bash
cd ~/2026b-cosc2767-a2-sg-team-15/server && source .venv/bin/activate

KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
IP=<your-elastic-ip>
SHA=$(git rev-parse --short HEAD)

sudo mkdir -p /etc/rmit-store
sudo tee /etc/rmit-store/api.env > /dev/null <<EOF
SECRET_KEY=$KEY
ALLOWED_HOSTS=$IP,127.0.0.1,localhost
DATABASE_URL=postgres://rmit:rmit@localhost:5432/rmit_store
CLIENT_URL=http://$IP
CORS_ALLOWED_ORIGINS=http://$IP
CSRF_TRUSTED_ORIGINS=http://$IP
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
APP_VERSION=1.0.0
GIT_COMMIT=$SHA
EOF

sudo chown root:root /etc/rmit-store/api.env
sudo chmod 600 /etc/rmit-store/api.env
```

Four notes, each of which cost time to learn:

- **`token_urlsafe`, not Django's `get_random_secret_key`.** Django's output
  contains `$ # & * ( )`. systemd parses this file itself rather than through
  a shell, so those end up literal; url-safe base64 sidesteps the question and
  is equally strong.
- **`DJANGO_SETTINGS_MODULE` is deliberately absent.** `config/wsgi.py` reads
  it before django-environ has parsed anything, so it is set in the systemd
  unit instead. Putting it here is too late, and the failure is a confusing
  `ImproperlyConfigured` rather than an obvious missing variable.
- **`localhost` in `DATABASE_URL`,** not the public IP. Routing a connection
  out to the internet and back to the same machine is slower and usually
  blocked.
- **Both `*_COOKIE_SECURE` are False** because this is plain HTTP. `prod.py`
  defaults them to True, and a secure cookie is never sent over `http://` — so
  the admin login accepts your password and bounces straight back to the login
  form with no error, which looks exactly like a wrong password. Turn them on
  the day TLS terminates in front of this.

### 3.1 Reading it back

The file is mode 600 and you are not root, so `source` fails with
`Permission denied`. Use:

```bash
set -a; eval "$(sudo cat /etc/rmit-store/api.env)"; set +a
export DJANGO_SETTINGS_MODULE=config.settings.prod
echo "${SECRET_KEY:0:12}..."      # non-empty means it loaded
```

`eval` is safe here: the file holds only `KEY=value` lines you generated, and
the values are url-safe base64 and IP addresses.

Forget this and `prod.py` refuses to start on the missing `SECRET_KEY`. That
is the boot guard working, not a failure — the same guard
`tests/integration/test_configuration.py` asserts.

---

## 4. Database and static files

```bash
python manage.py migrate
python manage.py seed_demo --demo-users \
  --admin-email admin@rmit.edu.au --admin-password 'RmitStore2767!'
python manage.py collectstatic --noinput
```

Expect `Products : 47` and `777 post-processed`.

**`collectstatic` must run under the same settings module as the server.**
Dev uses `StaticFilesStorage` and writes no manifest; prod uses whitenoise's
`CompressedManifestStaticFilesStorage` and requires `staticfiles.json`. Get
this wrong and `/static/admin/css/base.css` still returns **200** while
`/admin/login/` returns **500** — so a check that only tested static files
would pass a broken deployment. `777 post-processed` is the proof it ran
under prod; dev never prints it.

---

## 5. Serve it

### 5.1 Build the SPA

```bash
cd ../client
npm ci
npm run build
sudo cp -r dist/* /usr/share/nginx/html/
```

`dist/config.js` keeps its default `API_BASE_URL: "/api"` — nginx puts the
API on the same origin. The copy that matters from here on is
`/usr/share/nginx/html/config.js`.

### 5.2 Install the services

```bash
cd ~/2026b-cosc2767-a2-sg-team-15

sudo cp deploy/plan-b/rmit-api.service /etc/systemd/system/rmit-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now rmit-api
systemctl status rmit-api --no-pager

sudo cp deploy/plan-b/nginx-rmit-store.conf /etc/nginx/conf.d/rmit-store.conf
chmod o+x /home/ec2-user
sudo nginx -t
```

`nginx -t` will report **`duplicate default server`**. Amazon Linux's stock
`/etc/nginx/nginx.conf` contains its own port-80 `server` block, and nginx
keeps the first `default_server` it parses — `nginx.conf` is read before
`conf.d/`. Left in place, every request is answered by the stock 404 page,
including `/healthz/`, which makes it look like the proxy configuration was
never installed.

```bash
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak
sudo nano /etc/nginx/nginx.conf
```

Comment out the whole `server { ... }` block containing
`root /usr/share/nginx/html;` — around line 37, closing brace included.
Leave `include /etc/nginx/conf.d/*.conf;` alone; that is what loads the site
file.

```bash
sudo nginx -t && sudo systemctl reload nginx
```

`chmod o+x /home/ec2-user` gives the directory mode `drwx-----x`, which lets
nginx traverse to `server/media/` without exposing anything else. Needing it
at all is the argument for moving media to S3: the moment a second instance
exists, an image uploaded to one is a 404 from the other, and no permission
change fixes that.

---

## 6. Verify

### 6.1 On the instance

```bash
IP=<your-elastic-ip>
for p in /healthz/ /readyz/ /api/version/ /shop /config.js \
         /static/admin/css/base.css; do
  printf "%-32s %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' http://$IP$p)"
done
```

All six must be 200. Then check the media path end to end, using the URL the
API actually advertises rather than one typed by hand:

```bash
curl -s http://$IP/api/products/ | grep -o '"image_url":"[^"]*"' | head -3

U=$(curl -s http://$IP/api/products/ | grep -o '"image_url":"[^"]*"' \
    | head -1 | cut -d'"' -f4)
curl -s -o /dev/null -w "%{http_code}\n" "$U"
```

The URLs must be on the public IP **with no port**. Anything mentioning
`127.0.0.1:8000` means the `Host` header is not reaching Django, and every
product image will be broken in every browser while working perfectly from a
shell on the instance.

### 6.2 From a laptop — the real test

```bash
cd <repo>/server && source .venv/bin/activate

SMOKE_BASE_URL=http://<elastic-ip> \
SMOKE_SPA_BASE_URL=http://<elastic-ip> \
SMOKE_EXPECTED_COMMIT=$(git rev-parse --short HEAD) \
SMOKE_EXPECTED_VERSION=1.0.0 \
SMOKE_MEMBER_EMAIL=member@rmit.edu.au \
SMOKE_MEMBER_PASSWORD='DemoPass2767!' \
pytest -m smoke --no-cov -v
```

**23 passed.** Both tiers share an origin in Plan B, so both URLs are the
same value; they diverge once the tiers split.

Run it from a laptop rather than on the instance. Proving the path from
outside is the entire point of a smoke suite, and running it on the box
skips the network, the security group and nginx's public binding.

`--no-cov` matters: these tests execute no local application code, so a smoke
run measures near zero and overwrites `test-reports/coverage.xml`.

`SMOKE_EXPECTED_COMMIT` only matches if the instance is on the same commit as
the laptop. After pushing, `git pull` on the instance and rewrite
`GIT_COMMIT` in `api.env`, then restart the service.

---

## Troubleshooting

Every row below was hit during the session that produced this document.

| Symptom | Cause |
|---|---|
| SSH hangs, no error | security group port 22 still scoped to a previous network |
| `Permission denied (publickey)` on connect | not in the directory holding the `.pem`, or key under `/mnt/c/` |
| `Permission denied (publickey)` on `git clone` | no ssh-agent running; `eval "$(ssh-agent -s)"` then `ssh-add` |
| `status=203/EXEC` from systemd | venv is not at `server/.venv`, so the gunicorn path does not exist |
| Stock nginx 404 page on every path | the `default_server` block in `nginx.conf` is winning |
| `502 Bad Gateway` on `/api/` | gunicorn is down — `journalctl -u rmit-api -n 50` |
| `400` on every path | the public IP is missing from `ALLOWED_HOSTS` |
| `403` on `/media/` | `chmod o+x /home/ec2-user` did not run |
| `404` on `/media/` | the `alias` path does not match the checkout |
| `/admin/` returns 500 while static returns 200 | `collectstatic` ran under dev settings |
| Admin login loops with no error | `SESSION_COOKIE_SECURE` still True on plain HTTP |
| `Killed` during `npm run build` | out of memory; add swap or use `t3.small` |
| Config edited but nothing changed | systemd reads `EnvironmentFile` at start — `systemctl restart rmit-api` |
| Images broken in browser, `curl` returns 200 | stale browser cache from before the address changed; hard-refresh |

For anything nginx serves off disk, read the path it actually tried rather
than guessing:

```bash
sudo tail -5 /var/log/nginx/error.log
```

---

## After a Learner Lab session ends

The instance stops; the Elastic IP and the disk persist. On restart:

```bash
systemctl status rmit-api postgresql nginx --no-pager
curl -s http://<elastic-ip>/healthz/
```

Both services are `enabled`, so they start on boot and there is usually
nothing to do. If the Elastic IP was reallocated rather than re-associated,
rewrite `api.env` (step 3), `systemctl restart rmit-api`, and update the
`HostName` in your SSH config.

---

## What this tells us about the pipeline

Every step above is a step Plan F removes. Written out, the manual deploy is:

pull, install dependencies, load configuration, migrate, seed, collect
static, build the frontend, copy the bundle, install two service files,
reload two daemons, verify by hand.

Twelve ordered steps, each of which breaks the site differently when skipped —
and `collectstatic` breaks it in a way that still returns 200 to the most
obvious check. That is the argument for automation stated as a fact rather
than an opinion.

Three things stand out as pipeline requirements rather than conveniences:

- **The build does not belong on the server.** It can exhaust the instance,
  and it needs Node, which nothing else here does.
- **Configuration is the fragile part, not the code.** Of the thirteen
  troubleshooting rows above, nine are configuration or environment; two are
  code paths. Templating `ALLOWED_HOSTS` from instance metadata rather than
  retyping an IP is most of what Ansible buys in Plan C.
- **Media on local disk is a hard ceiling.** `chmod o+x` makes it work for
  exactly one instance. A second replica breaks the storefront intermittently,
  which is the S3 exercise.
