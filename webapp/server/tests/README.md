<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 08/09/2026
Last modified: 13/09/2026
Acknowledgement: Written with help from Claude (Anthropic). Every command
  here was run and every number checked by the author.
-->

# Backend tests

Twelve tests. Money and stock first, because that is where a bug costs the
store something.

## Scope

| Suite | Test | Boundary or property pinned |
|---|---|---|
| unit | money rounds half up at the cent | 10.005 up, 10.004 down, 2.675 up, two places kept |
| unit | tax only on taxable lines, rounded | 44.95 at 5% is 2.25 (the README's example), 0.10 gives 0.01, 0.09 gives 0.00, non-taxable is 0.00 |
| unit | Luhn at the length and checksum edges | 12 and 19 digits pass, 11 and 20 fail, one digit off fails, spaces ignored |
| unit | card valid to the end of its month | this month passes, last month fails, later month of an earlier year fails |
| integration | prices from the database, stock once | request lies about every price; subtotal 72.90, tax 2.25, total 75.15, both stocks down by one |
| integration | declined card | 402, no order row, stock unchanged, no email |
| integration | quantity vs stock | equal to stock passes and leaves 0, one over is 400 and stock untouched |
| integration | duplicate lines | two lines for one product become one line, stock taken once for the sum |
| integration | card number never kept | response and order row hold brand and last4 only |
| integration | line items snapshot | rename and reprice after purchase, the order still shows the original |
| smoke | probes and version | healthz 200, readyz 200 with database and storage ok, commit equals what was shipped |
| smoke | declined card post-deploy | full write path exercised, 402, nothing left behind |

Boundary values sit in a table inside each test, so one test is one Jenkins
row and every edge is still covered.

### Not here, on purpose

- Frontend unit tests and browser journeys: frontend workstream.
- Authorisation matrix, catalogue listing, config boot guards: real behaviour,
  cut to keep the suite small. The prod settings still refuse to boot without a
  real SECRET_KEY, that just isn't asserted here any more.
- Seeding and admin creation: management commands, proven by deploying.

## Running

From `webapp/server/` with the venv active and Postgres on `DATABASE_URL`
(SQLite cannot run `select_for_update`), or from the repo root inside the API
image, which is what CI does:

| Command | Runs |
|---|---|
| `pytest` | unit + integration, 10 tests, reports in `test-reports/` |
| `pytest -m unit` | the 4 pure-function tests |
| `SMOKE_BASE_URL=http://<host> pytest -m smoke --no-cov` | the 2 deployment checks |
| `docker compose -f compose.yaml -f compose.ci.yaml run --rm test` | the CI run |

Set `SMOKE_EXPECTED_COMMIT` to make the version check strict, and
`SMOKE_MEMBER_EMAIL` / `SMOKE_MEMBER_PASSWORD` to enable the declined-card
check (it skips without them).

## Coverage

Reported, not gated. `orders/payments.py` and `orders/services.create_order`
are the lines that matter and they are covered; the total is low because most
of the app is out of scope here.

## When it goes red

| Symptom | Probably |
|---|---|
| `inifile: None` | not in `webapp/server/` |
| `connection refused` on 5432 | Postgres not running |
| `Permission denied: test-reports/junit.xml` | the folder was created by root, `sudo chown -R $(id -u) webapp/server/test-reports` |
| smoke: `did not answer /healthz/` | nothing deployed at `SMOKE_BASE_URL` |