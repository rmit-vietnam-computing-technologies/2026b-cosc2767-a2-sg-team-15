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
records. Drafted with Claude (Anthropic) in a guided session; the decision
and its reasoning are the team's. Reference: assignment brief, Core
Requirement 2; Django databases documentation,
https://docs.djangoproject.com/en/5.2/ref/databases/
-->

# ADR 0002 — Where the database runs, per environment

**Status:** Accepted, 07/09/2026
**Tags:** `[REQ-2]` `[REQ-1]` `[ADV-1]` `[ADV-4]`

## Context

The brief allows the database tier to run either as a container or as a
managed service, and asks for the choice to be stated and justified. It
also sets a constraint that shapes everything else: uploaded media and any
other state on an instance becomes inconsistent the moment a second replica
exists. The database is the largest piece of state in the system.

Three facts about this application narrow the options:

- It requires real PostgreSQL. `select_for_update(of=("self",))` in the
  order service is a PostgreSQL feature; SQLite cannot run the integration
  suite, let alone production.
- Migrations must run in a controlled order relative to the code that
  depends on them. Two API replicas applying the same migration at once is
  a race; the roles run `migrate` from the playbook, never from a service
  entrypoint.
- The Learner Lab is the only AWS environment available, with a session
  clock and a credit budget. Anything that must survive a session ending
  has to live somewhere that persists.

Plan C introduced a `db_host` variable. When it is `localhost`, the
`database` role installs and configures PostgreSQL on the API instance;
any other value skips that role and the application connects to whatever
is there. This ADR records what the value should be, and where.

## Decision

Three environments, three answers.

| Environment | Database | Why |
|---|---|---|
| Developer laptop and CI | PostgreSQL 16 **container** | Real PostgreSQL, disposable, identical everywhere, no AWS dependency for a test run. Compose in Plan F step G. |
| Plan C (two plain instances) | PostgreSQL 16 **on the API instance**, `localhost` | A learning topology with one API replica. Keeping the database local keeps the security group surface at zero — it binds to loopback and has no rule — and keeps the playbook self-contained for a marker reproducing it. |
| Staging and production (Plan F) | **Amazon RDS** for PostgreSQL | State leaves the instances, which is the precondition for running more than one API replica behind a load balancer. Backups, point-in-time recovery, failover and patching become RDS's job rather than a playbook's. |

The `db_host` switch already implements this: an RDS endpoint in
`group_vars` disables the `database` role and nothing else changes. The
same `DATABASE_URL` shape reaches the application in all three cases.

## Consequences

**Good**

- The API tier becomes stateless in Plan F, so it can be replicated,
  replaced and rolled back without touching data. That is the property the
  orchestration requirement (REQ-9) and the blue/green strategy (ADV-3)
  both depend on.
- Backup and restore (ADV-4) is an RDS snapshot and a restore rehearsal,
  not a `pg_dump` cron job on an instance that may not exist tomorrow.
- The database credential moves to Secrets Manager or SSM Parameter Store
  alongside the RDS instance in CloudFormation (ADV-1), rather than a
  gitignored YAML file on a laptop.
- Plan C stays reproducible on a clean account with nothing but two EC2
  instances, which is what the brief asks a marker to be able to do.

**Costs and risks**

- RDS on the Learner Lab: instance classes and features are restricted, and
  a running RDS instance consumes credits whether or not it is used. The
  smallest available class is enough for this catalogue; the budget impact
  must be checked before Plan F relies on it.
- Migration ordering does not change: `migrate` still runs from the
  pipeline, once, before new application code takes traffic. RDS makes the
  data durable; it does not make a bad migration reversible. Zero-downtime
  migration practice (ADV-4) is a separate piece of work.
- Two configuration paths now have to be tested: `localhost` and an
  endpoint. The `database` role's skip condition is the only branch, and
  `readyz` checks the database either way, so a misconfigured endpoint
  surfaces as an unready instance rather than as a runtime error.
- Plan C's local database is not backed up. That is acceptable for a
  topology whose data is `seed_demo` output, and it is stated here so
  nobody mistakes it for a production posture.

## Alternatives considered

**Containerised PostgreSQL in staging and production, on a Swarm volume.**
Keeps everything in one orchestrator and costs nothing beyond the instance.
Rejected because the volume is still on an instance: replacing the node
that holds it is a manual data migration, and the brief's scalability and
rollback requirements are precisely about not being in that position.

**PostgreSQL on a dedicated EC2 instance managed by Ansible.** A middle
ground that separates state from the API tier without RDS. Rejected as the
worst of both — the operational burden of self-managed PostgreSQL with none
of the orchestration benefits, and a third instance to keep alive on the
Learner Lab clock.

## Related

- `docs/adr/0003-media-storage.md` — the same principle applied to
  uploaded files.
- `deploy/plan-c/group_vars/all.yml.example` — the `db_host` switch.
- `deploy/plan-c/roles/database/` — what `localhost` provisions.
