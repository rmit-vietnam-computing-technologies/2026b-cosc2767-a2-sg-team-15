<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 02/09/2026
Last modified: 02/09/2026
Acknowledgement: Adapted from Plan A of UPSTREAM-README.md, with Ubuntu and
  WSL2 specifics that the original (written cross-platform) does not cover.
-->

# Plan A — build and run the RMIT Store locally

**Goal.** The full three-tier stack running on one machine: Postgres, the Django
API, the Vue SPA. Nothing automated. This exists so we know what the pipeline
has to replace.

**Environment this was written against.** WSL2 Ubuntu 24.04, repository cloned
into the Linux filesystem at `~/work/`. Deltas for macOS and native Windows are
in the last section.

**Time.** About 40 minutes the first time. `npm install` and the 47 seed
photographs are most of it.

> Do not run this from `/mnt/c/...`. See §9.

---

## 0. Machine setup

Skip to §1 if you already have a Linux shell, a working `git` over SSH, and the
repository cloned somewhere on a Linux filesystem.

### 0.1 A Linux shell

**On Windows.** WSL2, not Git Bash. Git Bash runs the commands but cannot run
Ansible, which you need from Plan C onward.

```powershell
wsl --install -d Ubuntu
wsl --set-default Ubuntu
```

Reboot, set a UNIX username and password when prompted.

### 0.2 Git over SSH

HTTPS password auth was removed by GitHub in 2021, and a token in your shell
history is a token in your shell history.

```bash
ssh-keygen -t ed25519 -C "your.email@example.com"     # accept defaults
cat ~/.ssh/id_ed25519.pub
```

Paste the public key into GitHub → Settings → SSH and GPG keys → New SSH key.
Verify:

```bash
ssh -T git@github.com      # "Hi <user>! You've successfully authenticated"
```

### 0.3 Clone onto the Linux filesystem

**WSL users: this must be under `~`, never `/mnt/c/`.** Three reasons, and the
first is a hard blocker:

- You cannot `chmod 600` a file on the default `/mnt/c` mount — it reports
  `0777` whatever you do. `ssh` and Ansible both refuse a private key that
  permissive, and you will need `labsuser.pem` at `600` for every Ansible run
  in this assignment.
- WSL2 reaches `/mnt/c` over a 9P network protocol. `npm install` and
  `pip install -r requirements.txt` are many-thousand-small-file operations;
  expect several times the runtime, and the same for Docker bind mounts later.
- Git reports `dubious ownership` on `/mnt/c` because NTFS ownership looks
  foreign, and every file reads as mode `0777`, so git can record executable
  bits that upstream does not have.

```bash
mkdir -p ~/work && cd ~/work
git clone git@github.com:rmit-vietnam-computing-technologies/2026b-cosc2767-a2-sg-team-15.git
cd 2026b-cosc2767-a2-sg-team-15
git switch dev/backend

git config --global user.name  "Your Name"
git config --global user.email "your.email@example.com"
```

### 0.4 VS Code

Install the **WSL** extension (`ms-vscode-remote.remote-wsl`), then from the
repository in your Linux shell:

```bash
code .
```

Confirm the green **`WSL: Ubuntu`** badge, bottom-left. Without it you are
editing over `\\wsl$\` from Windows, which looks identical and behaves
differently.

Two things that catch people:

- **Extensions install per remote.** Python, Docker, YAML and Ansible all need
  installing again on the WSL side even though Windows shows them as installed.
- **Set the default terminal profile** to Ubuntu (WSL): `Ctrl+Shift+P` →
  *Terminal: Select Default Profile*. Otherwise `` Ctrl+` `` opens PowerShell
  inside a WSL window.

Sanity check in the integrated terminal:

```bash
uname -a     # Linux ... WSL2
pwd          # /home/<user>/work/...  — not /mnt/c/
```

---

## 1. Check the vendored tree survived the import

```bash
cd ~/work/2026b-cosc2767-a2-sg-team-15
git switch dev/backend
git log --oneline -3
git ls-files -s server/manage.py client/vite.config.js UPSTREAM-README.md
```

All three must read `100644`. A `100755` means the Windows copy picked up an
executable bit; fix it before it appears in every future diff:

```bash
git update-index --chmod=-x server/manage.py    # repeat per affected file
```

```bash
(cd server/seed_assets && ls *.jpg | wc -l)     # 47
```

If that is not 47, the seeder in §6 will run but every product will be
imageless, and you will not find out until §8.

---

## 2. Install the runtimes

**Ubuntu / Debian**

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
                    postgresql postgresql-contrib \
                    curl git

curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

`python3-venv` is a separate package on Ubuntu and is not installed by default.
Without it `python3 -m venv` fails with a message recommending `apt install`,
which is confusing because Python itself is clearly present.

**Fedora**

```bash
sudo dnf install -y python3 python3-pip \
                    postgresql-server postgresql-contrib \
                    curl git

curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo bash -
sudo dnf install -y nodejs
```

`venv` is built into Fedora's Python; there is no separate package.

**Both.** Node from the distribution repositories is far too old, so both paths
use NodeSource — the same method Plan B uses on EC2, which keeps the version
consistent between laptops and the server.

Verify:

```bash
python3 --version    # 3.11 or newer
node --version       # v22.x
npm --version
psql --version       # 16.x
```

> **Version drift matters more than distribution.** Ubuntu 24.04 ships Python
> 3.12, Fedora 41 ships 3.13, and Amazon Linux 2023 runs 3.11. Pin the team to
> **Python 3.12, Node 22, PostgreSQL 16** and match RDS to the same Postgres
> major version. A teammate on a different distribution costs you the six
> commands in this section; a teammate on a different Python costs you an
> afternoon in CI.

---

## 3. Start and configure Postgres

**Ubuntu.** The installer creates and starts a cluster for you. Under WSL there
is no systemd by default, so it is installed but not running, and it will not
survive a WSL restart:

```bash
sudo service postgresql start
sudo service postgresql status      # "online"
```

You will retype that first line every time you open a fresh WSL session. To
make it persistent instead, enable systemd once:

```bash
printf '[boot]\nsystemd=true\n' | sudo tee /etc/wsl.conf
```

then run `wsl --shutdown` in PowerShell and reopen. After that,
`sudo systemctl enable --now postgresql` works normally.

**Fedora.** No cluster is created at install time — you have to do it:

```bash
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql
```

Then fix authentication, because a fresh Red Hat family `initdb` writes a
`pg_hba.conf` that uses **`ident`** for TCP connections. Django connects over
TCP with a username and password and is refused:

```
FATAL:  Ident authentication failed for user "rmit"
```

```bash
sudo sed -i 's/^\(host.*\)ident$/\1scram-sha-256/' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl reload postgresql
grep '^host' /var/lib/pgsql/data/pg_hba.conf     # should say scram-sha-256
```

The `local ... peer` lines are deliberately left alone — that is what
`sudo -u postgres psql` uses, and changing them locks you out of the database.

This is the same fix Plan B applies on Amazon Linux 2023, which is also Red Hat
family. Whoever solves it here should write down what they did, because the
Ubuntu contributors will meet it for the first time on EC2.

**Both.** Create the role and database:

```bash
sudo -u postgres psql -c "CREATE ROLE rmit LOGIN PASSWORD 'rmit' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE rmit_store OWNER rmit;"
```

### Verify — and note the `-h localhost`

```bash
psql -h localhost -U rmit -d rmit_store -c "SELECT version();"
```

Password is `rmit`.

The upstream README gives this without `-h localhost`. On Ubuntu that fails
with **`Peer authentication failed for user "rmit"`**. Without a host, `psql`
uses the Unix domain socket, and Ubuntu's default `pg_hba.conf` sets
`local all all peer` — peer auth matches the database role against your *Linux*
username, and there is no Linux user called `rmit`. Passing `-h localhost`
forces a TCP connection, which `pg_hba.conf` handles with `scram-sha-256`
instead.

This is not a problem for the application. `DATABASE_URL` already specifies
`@localhost`, so Django connects over TCP and never touches the socket. It only
bites when you drive `psql` by hand — which you will, constantly, from here on.

---

## 4. Set up the API

```bash
cd ~/work/2026b-cosc2767-a2-sg-team-15/server

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
```

`.venv/` and `.env` are both gitignored. Read `server/.env.example` properly
before moving on — it is the best documentation in the repository, and every
variable in it becomes a decision the pipeline has to make. The defaults are
correct for local work; change nothing yet.

Two things in there that matter later:

- `DJANGO_SETTINGS_MODULE` is read from `.env` under `manage.py`, but **gunicorn
  never reads `.env` at all** — `wsgi.py` runs before anything loads it, and
  defaults to `config.settings.prod`. That asymmetry is deliberate, and it is
  why Plan B's gunicorn command passes settings explicitly.
- `USE_S3=False` writes uploads to `server/media/` on local disk. That is the
  thing that breaks the moment there are two backend replicas.

---

## 5. Create the schema

```bash
python manage.py migrate
```

Expect a wall of `Applying <app>.<migration>... OK`.

This command has to run on **every** deployment where a model changed, before
the new code starts serving. Remember where it sits in the sequence — it is the
single hardest constraint on the rollback strategy, because rolling code back
does not roll the schema back.

---

## 6. Seed the demo data

```bash
python manage.py seed_demo \
    --admin-email admin@rmit.edu.au \
    --admin-password 'RmitStore2767!' \
    --demo-users
```

Roughly a minute — it attaches 47 photographs. Add `--no-images` for a fast
re-run, `--flush` to wipe and start over. The command is idempotent, so running
it twice duplicates nothing.

You now have:

| Account | Credentials |
|---|---|
| Administrator | `admin@rmit.edu.au` / `RmitStore2767!` |
| Member | `member@rmit.edu.au` / `DemoPass2767!` |
| Seller | `merchant@rmit.edu.au` / `SellerPass2767!` |

Confirm it landed:

```bash
psql -h localhost -U rmit -d rmit_store -c "SELECT COUNT(*) FROM catalog_product;"
```

Expect 47.

---

## 7. Run the API

```bash
python manage.py runserver 0.0.0.0:8000
```

Leave it running. In a second terminal:

```bash
curl -s http://localhost:8000/healthz/    # {"status": "ok"}
curl -s http://localhost:8000/readyz/     # {"database": "ok", "storage": "ok"}
curl -s http://localhost:8000/api/version/
curl -s http://localhost:8000/api/products/ | head -c 300
```

Open in a Windows browser — WSL2 forwards `localhost` automatically:

- <http://localhost:8000/api/docs/> — Swagger UI. The entire backend is
  exercisable here with no frontend at all. This is where most of the
  integration test design in Step 4 comes from.
- <http://localhost:8000/admin/> — sign in as the administrator.

### Note the difference between the two health endpoints

`/healthz/` touches nothing and answers as long as the process is alive.
`/readyz/` opens a database cursor and checks storage, and returns **503** if
either is down. Liveness and readiness are different questions, and a load
balancer that probes the wrong one either drops healthy instances or routes
traffic to a broken one. Prove it to yourself now:

```bash
sudo service postgresql stop
curl -si http://localhost:8000/healthz/ | head -1     # 200
curl -si http://localhost:8000/readyz/  | head -1     # 503
sudo service postgresql start
```

That 30 seconds is worth more than reading about it, and it is the behaviour
our readiness tests in Step 5 assert.

---

## 8. Run the frontend

Third terminal:

```bash
cd ~/work/2026b-cosc2767-a2-sg-team-15/client
npm install
cp .env.example .env
npm run dev
```

Open <http://localhost:5173>. Products with photographs loading is proof that
browser → API → database → seeded media all connect.

Grey placeholder boxes mean the SPA is up and the API is not — check terminal
two.

Vite proxies `/api` and `/media` to `http://localhost:8000`, so the browser
sees one origin and CORS never arises. That mirrors the nginx config we write
in Plan B, and it is why CORS problems appear for the first time in Plan C when
the tiers are genuinely split.

---

## 9. Build the artifact, and the trick that makes deployment work

`npm run dev` is not deployment. Stop it and build for real:

```bash
npm run build            # produces client/dist/
ls -la dist/ dist/assets/
npx vite preview --port 4173
```

`client/dist/` is the deployable artifact — a folder of static files. There is
no Node process in production.

Now the important part. Note the hashed bundle filename in `dist/assets/`, then:

```bash
nano dist/config.js       # change API_BASE_URL to http://localhost:8000/api
```

Hard-reload <http://localhost:4173> with the network tab open. Requests now go
to `http://localhost:8000/api/products/`, the page behaves identically, and
**the hashed filename has not changed**. Byte-for-byte the same bundle.

That is the whole promotion story: build once in CI, deploy the same artifact to
staging and production, point it at a different API with a config file the web
server serves. Rebuilding per environment means the thing you tested is not the
thing you shipped.

`vite preview` reuses the dev proxy, so relative `/api` also works there.
Watch *where the requests go* in the network tab rather than whether the page
loads — on a real static server there is no proxy.

---

## Verification checklist

Everything below passes before Step 1 is done.

- [ ] `psql -h localhost -U rmit -d rmit_store -c "SELECT COUNT(*) FROM catalog_product;"` → 47
- [ ] `/healthz/` → 200; `/readyz/` → 200
- [ ] `/readyz/` → 503 with Postgres stopped, 200 again after starting it
- [ ] `/api/docs/` renders and a `GET /api/products/` from Swagger returns data
- [ ] `/admin/` accepts `admin@rmit.edu.au`
- [ ] <http://localhost:5173> shows products **with photographs**
- [ ] A product page shows image, price, stock and reviews
- [ ] `npm run build` produces `dist/`, and editing `dist/config.js` redirects the API without changing the bundle hash
- [ ] `git status --porcelain` shows nothing from `.venv/`, `node_modules/`, `dist/`, `media/`, `staticfiles/`

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Peer authentication failed for user "rmit"` | `psql` used the Unix socket. Add `-h localhost`. See §3. |
| `Ident authentication failed for user "rmit"` | Fedora only. `pg_hba.conf` still has `ident` on the `host` lines. See §3. |
| `could not connect to server: No such file or directory` | Postgres is not running. `sudo service postgresql start`, or on Fedora `sudo systemctl start postgresql`. |
| Fedora: `psql: FATAL: database "postgres" does not exist` | You skipped `sudo postgresql-setup --initdb`. |
| Fedora: nginx cannot reach gunicorn later on | SELinux is enforcing. `sudo setsebool -P httpd_can_network_connect 1`. Does not occur on Amazon Linux 2023, which ships SELinux permissive. |
| `ensurepip is not available` | Ubuntu only. `sudo apt install python3-venv`. |
| `django.db.utils.OperationalError` on `migrate` | Postgres down, or `DATABASE_URL` in `.env` disagrees with the role you created. |
| Products render but images 404 | `server/seed_assets/` did not copy, or the seeder ran with `--no-images`. Re-run with `--flush`. |
| Every API call fails from the SPA | API not running, or something else holds port 8000. Set `VITE_DEV_API_PROXY` in `client/.env`. |
| `npm install` takes many minutes | You are on `/mnt/c`. Move the repo into `~/`. |
| `EACCES` / permission errors from npm | Same cause. |
| Postgres gone after reopening WSL | No systemd. `sudo service postgresql start`, or enable systemd per §3. |

---

## What this tells us about the pipeline

Every manual step above is a step the pipeline has to remove. Recording the
mapping now because it is the skeleton of the report's requirement sections.

| Manual step here | Replaced by | Tag |
|---|---|---|
| §2 installing runtimes by hand | Ansible roles; then a base image that already has them | `REQ-7`, `REQ-2` |
| §3 creating role and database | CloudFormation provisions RDS; migrations own the schema | `ADV-1`, `REQ-1` |
| §4 `cp .env.example .env` and hand-editing | Secrets injected from SSM / Jenkins credentials, never a file on disk | `ADV-4` |
| §5 remembering to run `migrate` | An explicit ordered pipeline stage before the new code serves | `REQ-4` |
| §7 eyeballing `curl` output | The smoke suite, run automatically after every deploy | `REQ-5` |
| §8 `npm run build` on a laptop | A CI stage on an agent — building on a t3.micro runs it out of memory | `REQ-3`, `REQ-6` |
| §9 hand-editing `dist/config.js` | Rendered at container start, one artifact promoted unchanged | `REQ-2`, `REQ-4` |
| `USE_S3=False` writing to local disk | S3 plus an instance role, because replica two 404s on replica one's uploads | `REQ-9`, `ADV-1` |

---

## macOS

`brew install postgresql@16 && brew services start postgresql@16`. Homebrew
gives your account superuser rights on the cluster, so drop the
`sudo -u postgres` prefix and run `psql -d postgres -c ...` directly. `-h
localhost` is unnecessary but harmless. Homebrew already permits password
logins on localhost, so the `pg_hba.conf` edit does not apply.

## Native Windows

Workable for Plan A only. Use the official PostgreSQL installer and let it
start the service, run the two `CREATE` statements in *SQL Shell (psql)*
without the `psql -c` wrapper, and activate the venv with
`.venv\Scripts\activate`.

**Ansible has no Windows control node** — it is unsupported and does not run.
Requirement 7 needs WSL or a Linux VM regardless, so §0.1 is the better use of
the hour.