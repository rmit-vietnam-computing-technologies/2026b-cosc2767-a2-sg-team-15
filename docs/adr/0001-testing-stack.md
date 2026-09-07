<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 07/09/2026
Last modified: 07/09/2026
Acknowledgement: Format follows Michael Nygard's architecture decision
records. Records decisions made on 02/09/2026 when the suites were built;
drafted with Claude (Anthropic) in a guided session. References: pytest
documentation, https://docs.pytest.org/; pytest-django,
https://pytest-django.readthedocs.io/; assignment brief, Core Requirement 5.
-->

# ADR 0001 — Testing stack for the backend

**Status:** Accepted, 02/09/2026 (written up 07/09/2026)
**Tags:** `[REQ-5]` `[REQ-3]` `[REQ-6]` `[T15-BE-TEST]`

## Context

The repository ships with no tests. The brief makes writing them part of
the assessment and leaves tooling, structure and coverage target to the
team, on condition the choices are justified. Whatever is chosen has to
produce results Jenkins can publish (REQ-3, REQ-6), run identically on a
laptop and on an agent, and cover three named methodologies — unit,
integration and web UI — plus deployment smoke checks.

Django provides a test runner, `manage.py test`, built on `unittest`. It
would have been the zero-decision option.

## Decision

**pytest with pytest-django**, three marker-defined suites, and a coverage
gate applied in CI only.

| Choice | Over | Because |
|---|---|---|
| `pytest` + `pytest-django` | `manage.py test` | `parametrize` — the payment gateway has a table of card numbers and expected outcomes, and the authorisation matrix is four roles × every endpoint. Under `unittest` each cell is a method or a loop that stops at the first failure; under pytest each cell is one test with its own result line. Fixtures replace `setUp` inheritance, and `--junitxml` is native rather than a plugin. |
| markers `unit` / `integration` / `smoke` / `slow` | directory-only separation | Directories organise files; markers organise *runs*. `-m unit` for the pre-commit loop, `-m "not smoke"` as the default so a laptop with nothing deployed is green, `-m smoke` pointed at a URL after a deploy. `--strict-markers` makes a typo an error rather than an empty run. |
| `--junitxml` and `--cov-report=xml` in `addopts` | CI-only flags | What runs on a laptop is byte-identical to what runs on the agent. The one thing worse than no CI is CI that runs a different command than the developer did. |
| `--cov-fail-under=65` **added by CI**, not in `addopts` | gate everywhere | `pytest -m unit` covers a sixth of the code by design and reports ~16%. A threshold in `addopts` turns every legitimate subset into a red run, which trains people to pass `--no-cov` and throws the gate away. CI runs the same suite and adds one flag. |
| `freezegun` | mocking `date.today()` by hand | The card-expiry check compares against today. Without a frozen clock the expiry tests rot silently in whichever month the fixture card expires. |
| `requests` for smoke tests | Django's test client | Smoke tests must go *out* — through the network, the security group, nginx's public binding — or they prove nothing about the deployment. The in-process client skips all of it. |
| Real PostgreSQL for integration tests | SQLite | `select_for_update(of=("self",))` in the order service is PostgreSQL-only. A SQLite test database would pass tests the production database fails. |

Suite shape at the time of writing: 345 tests — 131 unit, 191 integration,
23 smoke, with 7 of the integration tests also marked `slow`. Overall
coverage 66%; `payments.py` 100%, `orders/services.py` 93%,
`orders/views.py` 90%, `core/permissions.py` 85%.

## Consequences

**Good**

- Every mutation test performed on the suite failed the expected tests and
  only those: removing the transaction around order creation, removing the
  `SECRET_KEY` boot guard, making readiness always return 200, serving the
  SPA without `try_files`. The suite catches the failures it was written
  for.
- The smoke suite ran unchanged against Plan B and Plan C — 23 passed on
  both — because it knows nothing about the topology, only the URL.
- Jenkins gets JUnit and Cobertura XML from the first run with no
  pipeline-specific configuration.

**Costs and risks**

- 65% is a ratchet, not an ambition. It sits just below the current figure
  so a regression fails the build, and it must move up as the merchant and
  accounts suites land. The number worth defending in the report is not the
  total: it is that the paths where a defect costs money or leaks data are
  near complete, while the total is held down by ~220 statements of
  management commands exercised by deploying, not by tests.
- Two known gaps, both recorded in HANDOFF: `merchants/services.py` at 21%,
  and `accounts` views and serializers at 64% / 53% — the register, sign-in
  and sign-out journey the brief names explicitly for end-to-end tests.
- Smoke tests cannot contribute coverage. They run out-of-process over
  HTTP, so `coverage.py` sees nothing; `create_admin` and `seed_demo` need
  in-process `call_command()` tests to register at all.
- One smoke test checks the shape of image URLs without fetching them. It
  passed once while the storefront showed no images. ADR 0003 forces the
  rewrite.
- Version ranges rather than exact pins while the suite is being built.
  Freeze to a lockfile once CI is green.

## Related

- `server/pytest.ini` — every option above, with the reasoning inline.
- `server/requirements-dev.txt` — the dependencies, separated from runtime
  so no test runner ships in the container image.
- `docs/TESTING.md` — how to run the suites; this ADR is why they look the
  way they do.
