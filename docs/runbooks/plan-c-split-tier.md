<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 07/09/2026
Last modified: 07/09/2026
Acknowledgement: Structure follows Plan C of UPSTREAM-README.md and the Plan B
runbook in this directory. Drafted with Claude (Anthropic) in a guided session
across 06/09 and 07/09; the author performed every step, hit every row of the
troubleshooting table, and verified the result.
-->

# Plan C — deploy the RMIT Store across two EC2 instances with Ansible

**This is the first automated deployment.** Everything Plan B did by hand,
`site.yml` now does in one command from a laptop — and does nothing at all
when run again against an instance that is already correct. That second
property is the point.

> Timing from the real sessions: the first run is dominated by three tasks —
> `npm ci`, the Vite build and `pip install`. A converged re-run does none
> of them.

Angle-bracketed values like `<web-elastic-ip>` are placeholders. Substitute
before pasting; bash reads `<x>` as a file redirect.

---

## What changes from Plan B

Same application, same nginx-in-front-of-gunicorn shape. The difference is a
network between the tiers.

```
internet → WEB  (Elastic IP)   nginx: SPA from disk; proxies
                                     /api /admin /healthz /readyz /media /static
                                          ↓ private IP, port 80
           API  (no public route) nginx: /media /static from disk;
                                        everything else → gunicorn :8000
                                  PostgreSQL on localhost
```

The browser only ever talks to the web instance. `config.js` sets
`API_BASE_URL` to the relative path `/api`, so the bundle carries no address
and no cross-origin request is ever made. Both nginx configs forward the
`Host` header unchanged, which is what lets Django build product image URLs
that work from a browser rather than only from a shell on the instance.

Five plays in `site.yml`, in dependency order: `common` on both hosts,
`database` and `api` on the API instance, `web` on the web instance, then a
verify play that fetches the storefront from the control node.

### Where this deliberately differs from Plan B and the upstream README

Three choices in Plan C are not what Plan B did or what
`UPSTREAM-README.md` describes. Each is a decision, not a drift.

**The SPA is served from `/var/www/rmit-store`, not `/usr/share/nginx/html`.**
Plan B and the upstream README use the nginx package's directory because,
by hand, it is the path of least resistance. Under Ansible it is the wrong
target for two reasons found the hard way. The package ships its own files
there — `404.html`, `50x.html`, `nginx-logo.png`, `icons/` — and a
recursive copy leaves the bundle mixed with them, so a stale file from any
previous deploy is indistinguishable from a current one. And a directory
the role does not own cannot be reasoned about: its initial mode is the
package's, its ownership is the package's, and a `dnf update nginx` can
change either. A directory the role creates has one owner and one source of
truth. The path is a single variable, `web_root`, and the nginx template
reads it, so nothing else knows the location.

**SSH to the API instance goes through the web instance, and the API has no
port open to the internet.** The upstream README and the first draft of
this inventory reached both instances over public addresses, with the API's
port 22 scoped to an admin `/32`. That worked, and it also meant the API's
public address — which the Learner Lab reassigns every session — sat in the
inventory, the SSH config and a security-group rule, all of which had to be
retyped on every restart. `ProxyJump` through the web instance reaches the
API over its private address, which is stable, and lets `api-sg` allow
port 22 only from `web-sg`. The inventory comment's claim that "nothing but
SSH crosses the internet" becomes literally true: nothing does.

**Each instance has its own read-only deploy key rather than borrowing the
operator's agent.** Plan B's runbook forwarded the laptop's agent for the
clone. That ties a deployment to whichever laptop is running it, which is
exactly the dependency Plan F removes by giving Jenkins a credential of its
own. A deploy key per instance is the same shape one step earlier. Agent
forwarding still works — `ansible.cfg` keeps `ForwardAgent=yes` — so a
control node without deploy keys is not blocked, only less reproducible.

---

## 0. Before you run anything

Every item in this section is a manual prerequisite the playbook assumes.
None of them are automated in Plan C; ADV-1 removes most of them.

### 0.1 Two instances

| Setting | Value |
|---|---|
| AMI | Amazon Linux 2023 |
| Type | `t3.small` — the Vite build OOMs on a micro even with swap |
| Key pair | the same pair for both |
| Auto-assign public IP | on, for both |
| IMDSv2 | Required (the default; the api role reads its own address from IMDS) |

Name them `web` and `api` in the console. Both go in the default public
subnet — the API instance is *restricted by security group*, not by
subnet, because a private subnet needs a NAT gateway the Learner Lab does
not readily provide.

### 0.2 Security groups — create these before launching

| Group | Port | Source |
|---|---|---|
| `web-sg` | 22 | your IP `/32` |
| `web-sg` | 80 | `0.0.0.0/0` |
| `api-sg` | 22 | **`web-sg`** — the group, selected from the dropdown |
| `api-sg` | 80 | **`web-sg`** — the group, selected from the dropdown |

PostgreSQL gets no rule; it binds to localhost.

The two `api-sg` rules must reference the *security group*, not a CIDR. In
the console's source field, leave the type on **Custom**, click the search
box and type `web` — a list of groups appears; pick `sg-… (web-sg)`. Typing
an address gives you a CIDR, which is wrong here.

A rule's source type cannot be changed in place. If you created `api-sg 22`
with a `/32` first, AWS refuses to edit it to a group reference
(`You may not specify a referenced group id for an existing IPv4 CIDR
rule`). Delete the row and add a new one.

With these rules the API instance has **no port open to the internet**. SSH
reaches it through the web instance (0.5), and application traffic reaches
it over the private address.

### 0.3 Elastic IP — web only

Allocate one and associate it with the web instance. That address goes in
two places (`inventory.ini` and `group_vars/all.yml`) and survives a
Learner Lab stop/start.

The API instance gets no Elastic IP on purpose. Its public address changes
on every session — three times across the two sessions that produced this
document — and nothing should depend on it. Its *private* address is what
matters, and that survives stop/start for the life of the instance.

### 0.4 Deploy keys — one per instance

The playbook clones the private repository onto both instances. Each needs
a read-only deploy key, generated on the instance, registered on the repo.

On each instance, as `ec2-user`:

```bash
ssh-keygen -t ed25519 -C "rmit-store-plan-c-$(hostname)" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

Paste the public key at **the repository → Settings → Deploy keys → Add
deploy key**, with *Allow write access* unchecked. Generate a fresh key for
the second instance; GitHub rejects a duplicate on the same repo.

Two traps, both hit:

- **Put it on the repo, not your account.** `ssh -T git@github.com` greeting
  you as `Hi <your-username>!` means the key landed in *Settings → SSH and
  GPG keys*. That gives the instance write access to everything you can
  reach. A deploy key greets you with the repo name instead.
- **`ssh -T` proves the key is registered somewhere, not that it can read
  this repo.** Verify with the thing the playbook actually does:

```bash
sudo dnf install -y git          # not there on a fresh AL2023; common installs it later anyway
git ls-remote git@github.com:rmit-vietnam-computing-technologies/2026b-cosc2767-a2-sg-team-15.git dev/backend
```

A SHA and `refs/heads/dev/backend` means the clone will work.
`Repository not found` means the key authenticated but has no grant here.

Why deploy keys rather than agent forwarding: forwarding works too, and
`ansible.cfg` keeps `ForwardAgent=yes` as a fallback, but it ties the deploy
to whichever laptop has the agent running. Deploy keys make the instances
self-sufficient, which is closer to how Plan F's Jenkins credential works.
The git tasks run with `become: false` so that either credential is visible
— `ansible_user` is already `ec2-user`, so the sudo hop bought nothing and
scrubbed `SSH_AUTH_SOCK`.

### 0.5 The control node

Ansible runs on your laptop — WSL, in the sessions that produced this — and
never on the instances. The managed nodes need SSH and Python, both of which
AL2023 ships. `ansible-galaxy` on an instance is the wrong machine.

```bash
ansible --version
cd deploy/plan-c
ansible-galaxy collection install -r requirements.yml
```

`requirements.yml` pins four collections the roles call. The full `ansible`
package bundles them; `ansible-core` does not, and the failure is a
module-not-found that names the module rather than the missing collection.

The key must be on the Linux filesystem, not under `/mnt/c/`, at mode 400:

```bash
ls -l ~/.ssh/project_keys.pem     # -r--------
```

Add the web instance to `~/.ssh/config`. The inventory's ProxyJump for the
API instance resolves this alias:

```
Host rmit-web
  HostName <web-elastic-ip>
  User ec2-user
  IdentityFile ~/.ssh/project_keys.pem

Host rmit-api
  HostName <api-private-ip>
  User ec2-user
  IdentityFile ~/.ssh/project_keys.pem
  ProxyJump rmit-web
```

`ssh rmit-api` then works from the laptop, through the web instance, with
the key never leaving the laptop. Accept the host key the first time.

Anything with VS Code Remote-SSH on Windows reads
`C:\Users\<you>\.ssh\config`, not the WSL one; keep a copy there if you
want editor access, and fix the `.pem`'s ACLs with `icacls`. Ansible does
not use either file for authentication — it reads
`ansible_ssh_private_key_file` from the inventory.

---

## 1. Configure

```bash
cd deploy/plan-c
cp inventory.ini.example inventory.ini
cp group_vars/all.yml.example group_vars/all.yml
```

Both copies are gitignored. They are the only place the real addresses and
the three secrets exist.

`inventory.ini`:

```ini
[web]
<web-elastic-ip>

[api]
<api-private-ip>

[api:vars]
ansible_ssh_common_args=-o ProxyJump=rmit-web
```

`group_vars/all.yml` — the two addresses and three generated secrets:

```yaml
web_public_ip: <web-elastic-ip>
api_private_ip: <api-private-ip>
```

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # django_secret_key
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # db_password
python3 -c "import secrets; print(secrets.token_urlsafe(12))"   # seed_admin_password
```

`api_private_ip` must be in `group_vars`, not only the inventory. The api
role overwrites it from IMDS for the API host, but the *web* host renders
`upstream { server {{ api_private_ip }}:80; }` from the group var and never
sees another host's inventory vars. Leave the placeholder and `nginx -t`
fails on an unresolvable upstream at the very end of the run.

Leave `cookie_secure: false`. There is no TLS in front of the web tier, and
`true` produces the silent admin-login loop from the Plan B table.

`repo_version` is the branch the instances will clone. It is not your local
checkout; push before you run.

Then:

```bash
ansible -i inventory.ini all -m ping
```

Two `pong`s. The API host answers via the jump.

### 1.1 Running this from another laptop, or on `main`

Nothing in the roles is specific to the machine that wrote them. What
*is* specific lives in three places, and a teammate running this on their
own laptop replaces exactly these:

| What | Where | Note |
|---|---|---|
| Their key file | `ansible_ssh_private_key_file` in `inventory.ini` | same key pair as the instances were launched with; mode 400, on the Linux filesystem |
| Their `Host rmit-web` | `~/.ssh/config` | the alias the ProxyJump resolves; the name is arbitrary but must match `[api:vars]` |
| Their admin `/32` | `web-sg` port 22 | the only security-group rule that depends on who is running it |

Deploy keys are per *instance*, not per operator — they carry over. So do
both `.example` files, the collections list and everything in `roles/`.

At merge, one value changes: `repo_version` in `group_vars/all.yml`, from
`dev/backend` to `main`. The instances clone that ref regardless of what
the operator has checked out, so a teammate who forgets this deploys the
backend branch and sees no error — the site comes up, on the wrong code.
Nothing else in the configuration knows which branch it is on.

Two instance-side facts survive a branch change and a change of operator:
`app_root` is the checkout path on the instances, and the deploy keys are
tied to the repository, not to a branch.

---

## 2. Run

```bash
ansible-playbook -i inventory.ini site.yml
```

What each play does, in the order it must happen:

**common** (both) — git and nginx; a 2 GB swap file with state-checked
`mkswap`/`swapon`; replaces `/etc/nginx/nginx.conf` with one that declares
no server block, because the packaged file claims `default_server` on port
80 and wins over anything in `conf.d/`.

**database** (api) — PostgreSQL 16, `initdb`, `pg_hba.conf` switched from
`ident` to `scram-sha-256` for TCP, role and database created, then a
`postgresql_ping` as the application user before anything depends on it.

**api** (api) — Python 3.11; the instance's own private address from IMDS;
clone; venv at `server/.venv` (the systemd unit hardcodes that path);
`/etc/rmit-store/api.env` root-owned 600; the unit; then `migrate`,
`seed_demo`, `collectstatic` in that order; media directory; `chmod 0711`
on the home directory so nginx can traverse in; the api nginx config; start
gunicorn; wait for `/readyz/` to return 200 — readiness, so the database is
proven reachable before the web tier is pointed here.

**web** (web) — Node 22; clone; `npm ci` and `npm run build`, both
conditioned on the checkout having changed; `config.js` templated *into
`dist/`* before publishing; the bundle copied to `/var/www/rmit-store` with
`mode: u=rwX,go=rX`; the web nginx config with `upstream` on the API
private address.

**verify** (from the laptop) — `GET /healthz/` through the web tier, then
`GET /` asserting on the SPA mount point.

Deprecation warnings from `ansible.posix.mount`, `community.postgresql` and
`amazon.aws` scroll past. They are upstream collection notices against a
newer `ansible-core`, not ours.

Evidence: `docs/evidence/REQ-7-01-plan-c-two-runs-converged.png` (first
run, left).

---

## 3. Run again — the convergence check

```bash
ansible-playbook -i inventory.ini site.yml
```

```
PLAY RECAP
<api-private-ip>   : ok=37   changed=0   unreachable=0   failed=0   skipped=4
<web-elastic-ip>   : ok=25   changed=0   unreachable=0   failed=0   skipped=4
```

`changed=0` on both hosts is the property that distinguishes configuration
management from a shell script: the playbook describes a state, and applying
it to a system already in that state does nothing. It did not come for free.
The first drafts of these roles reported six changed tasks on every run,
each for a different reason:

| Task | Why it never converged | Guard now |
|---|---|---|
| `Activate swap` | `swapon` on an active file exits 255 with `Device or resource busy`; the `failed_when` matched on `already` | check `swapon --show` first |
| `Template the API environment` | a render timestamp in the template header, so the file differed every time — and restarted gunicorn | timestamp removed |
| `Seed the demo catalogue` | `seed_demo` prints `Seeding complete` whether or not it did anything | marker file in `/var/lib/rmit-store` |
| `Install frontend dependencies` | `npm ci` deletes and reinstalls by design | `when: checkout changed or node_modules missing` |
| `Publish the bundle` / `Template the runtime configuration` | copy restored the placeholder `config.js` from `dist/`; template overwrote it; both changed, forever | template into `dist/` first |
| `Publish the bundle` / `Ensure the web root is traversable` | copy set the web root directory to 0644; a follow-up `file` task set it to 0755; both changed, forever | symbolic mode `u=rwX,go=rX` on the copy |

Evidence: `docs/evidence/REQ-7-01-plan-c-two-runs-converged.png` (second
run, right).

---

## 4. Verify

### 4.1 Through the web tier

```bash
curl -s http://<web-elastic-ip>/healthz/          # {"status":"ok"}
curl -s http://<web-elastic-ip>/readyz/           # {"database":"ok","storage":"ok"}
curl -s http://<web-elastic-ip>/api/version/      # {"version":"1.0.0","commit":"<short-sha>"}
curl -s http://<web-elastic-ip>/api/products/ | head -c 300
```

The `commit` must match `git rev-parse --short HEAD` on the branch you
pushed. The `image_url` values must start with `http://<web-elastic-ip>/`
— the public address, not `172.31.…`. If they carry the private address, a
`proxy_set_header Host` is wrong somewhere in the chain.

Evidence: `docs/evidence/plan-c/01-endpoints-through-web-tier.png`.

Then the storefront in a browser: the catalogue with product images, a
product page with price, stock and reviews. Images loading is the single
capture that proves the whole chain — SPA from web, `/api/` proxied to the
API tier, Django reaching PostgreSQL, URLs built from the forwarded `Host`,
media served off the API instance's disk.

Evidence: `docs/evidence/REQ-1-02-store-live-on-split-tier.png`,
`docs/evidence/plan-c/02-product-page-images-via-proxy.png`,
`docs/evidence/plan-c/03-product-reviews-from-database.png`.

### 4.2 From a laptop — the smoke suite

```bash
cd server && source .venv/bin/activate
which pytest                      # must be .../server/.venv/bin/pytest

SMOKE_BASE_URL=http://<web-elastic-ip> \
SMOKE_SPA_BASE_URL=http://<web-elastic-ip> \
SMOKE_EXPECTED_COMMIT=$(git rev-parse --short HEAD) \
SMOKE_EXPECTED_VERSION=1.0.0 \
SMOKE_MEMBER_EMAIL=member@rmit.edu.au \
SMOKE_MEMBER_PASSWORD='DemoPass2767!' \
pytest -m smoke --no-cov
```

**23 passed** — the same suite, the same count as Plan B, against a topology
it knows nothing about. The suite runs from `server/` (the `inifile: None`
trap) and needs the venv active; a system-wide `pytest` finds no
`rest_framework` and fails while loading `conftest.py`.

`SMOKE_EXPECTED_COMMIT` is the test that matters most: it asserts
`/api/version/` reports the build that was just deployed, which is the
ADV-3 mechanism for confirming a cutover from outside the instance.

Evidence: `docs/evidence/REQ-5-04-smoke-green-against-split-tier.png`.

### 4.3 The split is real

Nothing above distinguishes two instances from one. This does:

```bash
curl -sI --max-time 5 http://<api-public-ip>/healthz/ ; echo "exit $?"   # exit 28: timed out
ssh rmit-web 'curl -s http://<api-private-ip>/healthz/'                   # {"status":"ok"}
ssh rmit-api 'sudo systemctl is-active rmit-api postgresql'               # active, active
ssh rmit-web 'sudo systemctl is-active nginx'                             # active
```

The first line is the security group doing its job: the packet is dropped,
nothing answers, curl gives up. The second is the same endpoint answering
from inside the VPC. The instance has a public address — the Learner Lab
assigns one — and nothing listening to it.

Evidence: `docs/evidence/plan-c/04-api-unreachable-from-internet.png`.

---

## Troubleshooting

Every row was hit across the two sessions that produced this document.

### Reaching the instances

| Symptom | Cause |
|---|---|
| Ansible `UNREACHABLE` at a random task, `Connection timed out during banner exchange`, while a single `ssh` works | the Learner Lab session ended under the run, or the path drops connections at a low rate — `retries = 3`, `timeout = 60` and `ControlPersist=300s` in `ansible.cfg` are the mitigation |
| Same, but only through the ProxyJump | `api-sg` has no port-22 rule sourced from `web-sg`; test from the web box with `timeout 5 bash -c '</dev/tcp/<api-private-ip>/22'` |
| `UNPROTECTED PRIVATE KEY FILE` from Ansible while `ssh` works | key is mode 0644; `chmod 400`, and move it off `/mnt/c/` if it will not stick |
| `Connection timed out` to the API public address | the Learner Lab reassigned it; use the private address via ProxyJump and stop caring |
| `ssh -v` works, Ansible fails, no obvious difference | the control socket predates a config change — `rm -f ~/.ansible/cp/*` |
| Empty error after `reached over ssh:` | a new connection was dropped, not refused — same as the first row |

### GitHub

| Symptom | Cause |
|---|---|
| `Permission denied (publickey)` on the git task | no deploy key on that instance, or the task still runs under `become` and cannot see the credential |
| `ssh -T git@github.com` says `Hi <username>!` | the key is on your account, not the repo's deploy keys — move it |
| `git ls-remote` says `Repository not found` | the key authenticated but has no grant on this repo |
| `git: command not found` on a fresh instance | expected; install it for the check, `common` installs it anyway |

### The control node

| Symptom | Cause |
|---|---|
| `ansible-galaxy: command not found` | you are on an instance; collections install on the laptop |
| `community.general.yaml callback plugin has been removed` | community.general ≥ 12 — `result_format = yaml` in `ansible.cfg` replaces `stdout_callback = yaml` |
| module not found for `ec2_metadata_facts`, `postgresql_*`, `npm`, `mount` | collections not installed — `ansible-galaxy collection install -r requirements.yml` |
| `bash: api-public-ip: No such file or directory` | a `<placeholder>` pasted literally |
| `ModuleNotFoundError: No module named 'rest_framework'` on the smoke run | wrong `pytest` — activate `server/.venv`, check `which pytest` |

### AWS console

| Symptom | Cause |
|---|---|
| `You may not specify a referenced group id for an existing IPv4 CIDR rule` | a rule's source type is immutable; delete and recreate |
| Instant `Connection refused` on a port nothing listens on | the rule is right — refused means the packet arrived. A hang means it was dropped |

### The playbook

| Symptom | Cause |
|---|---|
| `swapon: /swapfile: swapon failed: Device or resource busy` | already active; the guard checks `swapon --show` now |
| Two tasks with the same name, one skips and the other fails | an edit added the new task without removing the old one |
| Handler `Reload nginx` never ran after an interrupted run | handlers are notified by `changed`; the next run reports `ok` and does not re-notify — use `--force-handlers` |
| Play recap shows a host with `ok=0` and the later plays empty | that host failed in `common`, so it was removed from every subsequent play |

### nginx on the web tier

| Symptom | Cause |
|---|---|
| `403 Forbidden` on every path, error log says `Permission denied` | a numeric `mode` on the directory copy stripped the traversal bit from the web root; `namei -l <path>` shows which directory — fix is `mode: u=rwX,go=rX` |
| `403` with `directory index … is forbidden` | no `index.html` at the root — the copy nested `dist/` one level down (trailing slash on `src`) |
| Stock nginx 404 on every path | the `default_server` block in `nginx.conf` — `common` replaces the file |
| `nginx -t` fails on `upstream` | `api_private_ip` still a placeholder in `group_vars/all.yml` |
| verify play passes, browser shows 403 | `/healthz/` is proxied; that is why the second verify task fetches `/` |

For anything nginx serves off disk, read the path it actually tried:

```bash
sudo tail -5 /var/log/nginx/error.log
namei -l /var/www/rmit-store/index.html
```

---

## After a Learner Lab session ends

Both instances stop. On restart:

| | |
|---|---|
| Web Elastic IP | re-attaches; nothing to change |
| API public IP | new one; irrelevant with ProxyJump |
| Private IPs | unchanged |
| Disks, services, deploy keys, security groups | unchanged |

Give sshd a minute after the console says *Running* — the state flips
before the status checks pass, and connecting into that window produces
the banner-exchange timeout from the troubleshooting table.

Then `ansible -m ping`, and if you want proof the state held, the playbook
once more: `changed=0`.

---

## What this tells us about the pipeline

Plan B's runbook counted twelve manual steps. Plan C replaces them with one
command, and the interesting findings are about what the one command still
depends on.

**The control node is the weak point.** Two afternoons were lost to
connections between a laptop and AWS: the Learner Lab session ending
mid-run, a campus network that drops SSH at a low rate, addresses that
changed under the inventory. None of it was the playbook. A control node
inside the VPC — which is what Jenkins becomes in Plan F — sees none of it.

**Every hand-typed address is a bug waiting.** Two addresses are supplied by
hand in Plan C, and one of them moved three times. The api role already
reads its own address from IMDS rather than trusting the inventory; ADV-1
makes both addresses stack outputs.

**Idempotence is a property you build, not one you get.** Six tasks failed
to converge in the first draft, each for a different reason: an error-string
match, a timestamp, a command that lies about what it did, a tool that
reinstalls by design, and two pairs of tasks undoing each other. The table
in section 3 is the record. Each fix is small; none was obvious from the
green first run.

**The web tier is fighting its own package.** `common` replaces the
packaged `nginx.conf`; the bundle deploys to `/var/www` to stay clear of
the packaged web root; the copy needs a symbolic mode to avoid breaking the
directory it writes to. A container image ships exactly the nginx config it
wants and none of this exists — which is a concrete argument for REQ-2 that
Plan B could not make.

**The build is still on the wrong machine, and now there are two of them.**
Both instances clone the full repository; one compiles the frontend on a
production box. Build once in CI, ship an artifact: Plan F.

**Media on local disk is one replica away from breaking.** Unchanged from
Plan B, and unchanged on purpose — see `docs/adr/0003-media-storage.md`.