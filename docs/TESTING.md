<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 02/09/2026
Last modified: 02/09/2026
Acknowledgement: Drafted with Claude (Anthropic) in a guided session; every
  command in this file was run and its output verified before being written
  down. Tooling choices are justified separately in docs/adr/0001-testing-stack.md.
-->

# Running the test suites

How to run every suite in this repository, what each one proves, and what to
do when one goes red. **Why** these tools were chosen belongs in
`docs/adr/0001-testing-stack.md`; this file is only about operating them.

Configuration lives in `server/pytest.ini` and `server/.coveragerc`. Neither
CI nor a laptop passes extra flags, with one deliberate exception (the
coverage gate, below), so what you run here is what the pipeline runs.

---

## Quick reference

Every command assumes you are in `server/` with the virtualenv active.

| Command | Runs | Time |
|---|---|---|
| `pytest` | everything except smoke — 322 tests | ~10s |
| `pytest -m unit` | 131 pure-function tests, no database | ~0.4s |
| `pytest -m integration` | 191 API-and-database tests | ~5s |
| `pytest -m "not slow"` | 338 tests, skipping the subprocess boot checks | ~5s |
| `pytest -m smoke --no-cov` | 23 checks against a deployed URL | ~3s |
| `pytest --cov-fail-under=65` | the full suite plus the coverage gate — what CI runs | ~10s |

---

## Before anything runs

**Be in `server/`.** `pytest.ini` lives there, and pytest finds its config by
walking up from wherever you invoke it. Run from the repository root and it
finds nothing: no `DJANGO_SETTINGS_MODULE`, no markers, no coverage. The
giveaway is `inifile: None` and `rootdir:` pointing at the repository root
instead of `server/`.

**Activate the virtualenv.** Without it you get the system interpreter, which
has no Django, so collection dies on `ModuleNotFoundError: No module named
'rest_framework'` and `--no-cov` is rejected as an unknown argument. The
giveaway is a missing `(.venv)` in the prompt, and a plugin list with no
`django-` or `cov-` in it.

```bash
cd ~/work/2026b-cosc2767-a2-sg-team-15/server
source .venv/bin/activate
sudo service postgresql start
```

First time on a machine:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

---

## Test loop

```bash
pytest
```

```
322 passed in 9.90s
TOTAL   1917   576   312   34   66.1%
```

Smoke is excluded automatically — `-m "not smoke"` is in `addopts`, because
those tests need something deployed and a laptop usually has nothing.

While iterating on one thing, the fast loop is worth knowing:

```bash
pytest -m unit                              # 0.4s, no database at all
pytest tests/integration/test_checkout.py   # one file
pytest -k "decline"                         # one idea, across files
pytest -x --ff                              # stop at first failure, failures first
```

`-k "decline"` matches 23 tests across the unit and integration suites, and is
usually a better filter than remembering which file something lives in.

---

## Unit — 131 tests

Pure functions. No database, no network, no Django test client.

```bash
pytest -m unit
```

```
131 passed, 214 deselected in 0.38s
```

Covers the payment gateway in isolation (Luhn, brand detection, expiry, CVC
length, the decline table) and the server-side money helpers (tax, line
totals, rounding). `apps/orders/payments.py` sits at 100%.

Frozen clock, so a card that expires next year does not quietly start failing
the suite on a date nobody chose.

---

## Integration — 191 tests

The API and the database together, through Django's test client. Each test
runs in a transaction that is rolled back afterwards, so order does not
matter and nothing leaks between them.

```bash
pytest -m integration
```

```
191 passed, 154 deselected in 5.13s
```

| File | Proves |
|---|---|
| `test_catalog_api.py` | the shop endpoint reads real rows — the API-to-database connection |
| `test_checkout.py` | stock, server-side totals, and that a declined card leaves nothing behind |
| `test_authorisation.py` | every endpoint against all four roles, plus queryset scoping |
| `test_order_lifecycle.py` | cancellation, restocking, and the one-way door on a cancelled line |
| `test_reviews.py` | moderation recomputes ratings everywhere at once |
| `test_configuration.py` | production boot guards, the host header, readiness failure |

The authorisation matrix is parametrised, so a failure names the endpoint and
the role rather than an index:

```
FAILED test_authorisation_matrix[merchant-POST /api/manage/brands/]
```

### The slow subset

Seven tests in `test_configuration.py` start a real Python subprocess to
prove `config.settings.prod` **refuses to boot** on a default `SECRET_KEY` or
an empty `ALLOWED_HOSTS`. They cost about a second each.

```bash
pytest -m "not slow"     # skip them in a tight loop
pytest -m slow           # just those seven
```

Do not skip them in CI. A process that refuses to start is the mechanism that
stops a misconfigured deployment from ever passing a health check.

---

## Smoke — 23 checks

These are the only tests that talk to a **deployed URL over HTTP**. They test
a deployment, not the code: gunicorn, nginx, whitenoise, the database
connection string, environment variables, the reverse proxy. None of it is
visible to the integration suite, which imports the application rather than
connecting to one.

### You need a target

Without `SMOKE_BASE_URL` the whole suite skips, by design:

```
23 skipped, 322 deselected in 0.11s
```

With the variable set and nothing listening, a session-scoped fixture polls
`/healthz/` and then fails once, with the same message repeated per test:

```
http://localhost:8000 did not answer /healthz/ within 60s. Last result:
ConnectionError. Is anything listening on that address? Set SMOKE_WAIT=5
to fail faster while working locally.
```

That is the suite working, not a bug. It waits because gunicorn takes a
second or two to bind after a deploy script starts it, and without the wait
the first assertion would lose the race and report a failed deployment that
actually succeeded.

### Running it

```bash
SMOKE_BASE_URL=http://127.0.0.1:8000 pytest -m smoke --no-cov
```

```
16 passed, 7 skipped, 322 deselected in 2.87s
```

**Always pass `--no-cov`.** These tests execute no local application code, so
a smoke run measures near zero and overwrites `test-reports/coverage.xml`
with that figure.

Everything the checks need:

| Variable | Effect if unset |
|---|---|
| `SMOKE_BASE_URL` | the whole suite skips |
| `SMOKE_SPA_BASE_URL` | the 6 frontend checks skip |
| `SMOKE_EXPECTED_COMMIT` | the deployed-commit check skips |
| `SMOKE_EXPECTED_VERSION` | the deployed-version check skips |
| `SMOKE_MEMBER_EMAIL` / `SMOKE_MEMBER_PASSWORD` | the 2 authenticated checks skip |
| `SMOKE_TIMEOUT` | defaults to 10s per request |
| `SMOKE_WAIT` | defaults to 60s waiting for the deployment |

The API and SPA origins are separate variables because they are only the same
host behind a single nginx. Once the tiers are split they differ, and a suite
that assumed otherwise would test the API twice and call the frontend healthy
without ever contacting it.

### A local target

Optional. The suite's real first run is against EC2, but standing this up
locally is a faithful rehearsal.

```bash
# once
python manage.py migrate
python manage.py seed_demo --demo-users \
  --admin-email admin@rmit.edu.au --admin-password 'RmitStore2767!'

DJANGO_SETTINGS_MODULE=config.settings.prod \
SECRET_KEY='local-smoke-target-not-the-default' \
ALLOWED_HOSTS='127.0.0.1,localhost' \
python manage.py collectstatic --noinput

# serve
DJANGO_SETTINGS_MODULE=config.settings.prod \
SECRET_KEY='local-smoke-target-not-the-default' \
ALLOWED_HOSTS='127.0.0.1,localhost' \
APP_VERSION='1.4.2' GIT_COMMIT="$(git rev-parse --short HEAD)" \
DATABASE_URL='postgres://rmit:rmit@localhost:5432/rmit_store' \
gunicorn config.wsgi:application --bind 127.0.0.1:8000
```

Then from a second terminal:

```bash
SMOKE_BASE_URL=http://127.0.0.1:8000 \
SMOKE_EXPECTED_COMMIT=$(git rev-parse --short HEAD) \
SMOKE_MEMBER_EMAIL=member@rmit.edu.au \
SMOKE_MEMBER_PASSWORD='DemoPass2767!' \
pytest -m smoke --no-cov
```

Warning:

**`collectstatic` must use the same settings module as the server.** Dev uses
`StaticFilesStorage`; prod uses whitenoise's manifest storage and needs
`staticfiles.json`, which dev never writes. Get this wrong and
`/static/admin/css/base.css` still returns **200** while `/admin/login/`
returns **500** — so a suite that only checked static files would pass the
broken deployment. `test_the_admin_login_page_renders` is what catches it.

**gunicorn does not read `.env`.** Every variable has to be on the command
line or in the systemd unit. That is deliberate: it is the same discipline a
container needs, and finding out here is cheaper than finding out on EC2.

---

## Coverage

Written on every run to `test-reports/coverage.xml` (Cobertura, for Jenkins)
and printed to the terminal. Measured over `apps/` only — the test code,
migrations and settings are excluded, because covering your own tests inflates
the number without telling you anything.

```bash
pytest --cov-fail-under=65
```

```
Required test coverage of 65% reached. Total coverage: 66.02%
322 passed in 7.14s
```

The gate is **not** in `addopts`, on purpose. A marker subset is a legitimate
way to run this suite, and `pytest -m unit` reports about 16% because it
exercises a sixth of the code deliberately. A threshold in `addopts` turns
that into a red run, which teaches people to pass `--no-cov` and throws the
gate away entirely. CI runs the identical suite and adds the flag.

Where it matters:

| Module | Coverage |
|---|---|
| `apps/orders/payments.py` | 100% |
| `apps/reviews/views.py` | 96.6% |
| `apps/orders/services.py` | 92.9% |
| `apps/orders/views.py` | 90.1% |
| `apps/core/permissions.py` | 84.7% |
| **Total** | **66.0%** |

The overall figure is held down by ~222 statements of management commands at
0%, which are exercised by deploying rather than by tests. The defensible
claim is not the total; it is that the paths where a defect costs money or
leaks data are near complete.

### Capturing coverage for the report

Reports reflect **whichever command ran last**. A partial run leaves partial
numbers in `coverage.xml` and on screen — `-m integration` alone reports
`payments.py` at 71.4% instead of 100%, because the unit tests that cover it
were deselected.

Before any screenshot, run the full command once:

```bash
pytest --cov-fail-under=65
```

---

## When something goes red

| Symptom | Cause |
|---|---|
| `ModuleNotFoundError: rest_framework` | virtualenv not active |
| `inifile: None`, `rootdir` is the repo root | not in `server/` |
| `unrecognized arguments: --no-cov` | system pytest, not the venv's |
| `connection refused` on port 5432 | `sudo service postgresql start` |
| Coverage lower than expected | a marker subset ran last; rerun plain `pytest` |
| A 301 where you expected 200 | missing trailing slash; the router generates one, and a redirect drops the request body |
| Smoke: `did not answer /healthz/` | nothing deployed at `SMOKE_BASE_URL` |
| Smoke: admin 500, static 200 | `collectstatic` ran under a different settings module |
| Smoke: `image_url` on `127.0.0.1` | proxy is not forwarding the real Host header |

### Test isolation

If a failure looks order-dependent, run the suite in parallel. Different
order, separate databases per worker:

```bash
pytest -n 4 --no-cov
```

322 should still pass. Do not adopt this as the default — per-worker database
setup makes it slower than serial at this size (17s against 7s).

---

