<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 08/09/2026
Last modified: 09/09/2026
Acknowledgement: Written with help from Claude (Anthropic). I ran every
  command in here and checked every number myself. Scope comes straight
  from Core Requirement 5 of the brief.
-->

# Backend tests: what's here and why

## Scope

Short version: Core Requirement 5 of the brief has a list of the tests it
wants for this app. That list is the spec. Every suite below exists because
a line in that list asks for it, and I didn't test anything the brief
doesn't mention. That's the boundary.

| Brief asks for | File | Functions | Cases |
|---|---|---:|---:|
| *Unit: the payment gateway logic in isolation (card validation, brand detection, expiry, decline codes)* | `unit/test_payments.py` | 26 | 99 |
| *Unit: server-side tax and total calculation* | `unit/test_money.py` | 9 | 31 |
| *Integration: the shop endpoint returns products, proving the API-to-database connection* | `integration/test_catalog_api.py` | 15 | 15 |
| *Integration: placing an order decrements stock and computes the total server-side; a declined card leaves no order behind and takes no stock* | `integration/test_checkout.py` | 18 | 20 |
| *Integration: authorisation holds, so anonymous / member / seller / admin get the status codes they should* | `integration/test_authorisation.py` | 10 | 47 |
| *Test the basic failure modes: misconfiguration that only shows up when deployed (wrong ALLOWED_HOSTS etc), health and version endpoints* | `integration/test_configuration.py` | 20 | 20 |
| *Smoke: /healthz/ and /readyz/ return healthy, /api/version/ reports the build you just deployed; missing static files; wrong API URL* | `smoke/test_deployment.py`, `smoke/test_spa.py` | 23 | 23 |
| | **Total** | **121** | **255** |

"Cases" is what Jenkins counts. A parametrised function reports once per
parameter set, so `test_payments` is 26 functions run over the brief's card
table, and the auth matrix is literally one function run over 9 endpoints x
4 roles (36 of that file's 47 cases). Nobody sat down and wrote 255 tests.

### Deliberately not tested

- **Frontend unit tests and the Web UI / e2e journeys.** Frontend
  workstream's job, not this folder's.
- **Order cancellation, restocking, review moderation, wishlist.** Real app
  behaviour, but the brief doesn't name it and the pipeline doesn't depend
  on it. I had tests for these and pulled them to keep things scoped. The
  coverage ratchet went from 65 to 60 because of that.
- **Every endpoint.** The auth matrix does one endpoint per permission class
  (public, logged in, admin only, seller surface, and the one admin-only
  action inside the seller surface). Routes that share a permission class
  are one equivalence partition, so testing one of them covers the class.
  Whether each viewset is wired to the right class gets covered by the
  scoping tests in the same file and by the feature suites.
- **App correctness beyond the above.** The pipeline is the deliverable. If
  I hit an upstream bug it goes in the report under Known Bugs, not a fix here.

## Running it

Everything assumes you're in `webapp/server/` with the venv active and a
PostgreSQL reachable at `DATABASE_URL`. SQLite won't work, the order code
uses `select_for_update`. Or skip all that and run it inside the API image,
which is what CI does: `docker compose -f compose.yaml -f compose.ci.yaml run --rm test`
from the repo root.

| Command | What runs |
|---|---|
| `pytest` | unit + integration, coverage written to `test-reports/` |
| `pytest -m unit` | the 130 pure-function cases, no database, under a second |
| `pytest -m integration` | the 102 API + database cases |
| `pytest --cov-fail-under=60` | what CI runs: everything plus the coverage gate |
| `SMOKE_BASE_URL=http://<host> pytest -m smoke --no-cov` | the 23 deployment checks against a live URL |

Smoke is off by default (`-m "not smoke"` in `pytest.ini`) because it needs
something deployed. No `SMOKE_BASE_URL` and it skips; set it with nothing
listening and it waits up to 60s for `/healthz/` then fails once.

## Coverage

Measured over `apps/` only (`.coveragerc`), so test code, migrations and
settings don't count. The gate is 60% and it's on the CI command line rather
than in `pytest.ini`, so running a marker subset locally doesn't go red.

The number I'd actually defend isn't the total. It's that
`orders/payments.py` is at 100% and `core/permissions.py` at 85%, which are
the bits where a bug costs money or leaks data. The total is dragged down by
management commands (you exercise those by deploying, not by tests) and by
the stuff I listed as out of scope.

## When it goes red

| Symptom | Probably |
|---|---|
| `ModuleNotFoundError: rest_framework` | venv not active |
| `inifile: None` | you're not in `webapp/server/` |
| `connection refused` on 5432 | Postgres isn't running |
| coverage lower than expected | a marker subset ran last, rerun plain `pytest` |
| smoke: `did not answer /healthz/` | nothing deployed at `SMOKE_BASE_URL` |
| smoke: admin 500 but static 200 | `collectstatic` ran under a different settings module than the server |
