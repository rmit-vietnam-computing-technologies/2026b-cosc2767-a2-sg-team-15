<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 02/09/2026
Last modified: 02/09/2026
Acknowledgement: File header format is prescribed by the assignment brief.
-->

# Team 15 contribution conventions

## 1. File header

Every file **we wrote or substantially modified** carries the header below.
Files we did not touch are left exactly as imported — that untouched state is
what proves authorship, so do not "tidy" a vendored file.

```
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: 
ID: 
Created  date: 
Last modified: 
Acknowledgement: <what you used — docs, Stack Overflow answers, an LLM, a teammate>
```

Note `Created  date` has two spaces. That is how the brief writes it; keep it.

### Comment syntax by file type

| File type | Syntax | Placement |
|---|---|---|
| Python, YAML, shell, Dockerfile, nginx, `.ini`, `.cfg`, Makefile | `#` | Top of file. **In shell and Python scripts, immediately after the shebang, never above it.** |
| JavaScript, Vue `<script>`, Terraform, CloudFormation (YAML) | `/* */` or `#` | Top of file |
| Markdown, HTML | `<!-- -->` | Top of file |
| JSON | none | **Omit the header.** JSON has no comments. |

Bump `Last modified` when you change a file. Nobody will chase you for it, but
a file dated three weeks before its last real edit looks careless in a report
that is partly marked on professionalism.

---

## 2. Marker tags

Every non-obvious decision in a config or script gets a one-line marker
comment. Two parts, both greppable:

```
# [T15-BE-WSGI][REQ-2] bind 0.0.0.0 — the container namespace is the boundary, not loopback
```

- `T15-BE-WSGI` — **topic**. `Ctrl+Shift+F` for `T15-BE` finds all backend
  decisions; `T15-BE-WSGI` narrows to the WSGI/gunicorn ones.
- `REQ-2` — **assignment requirement** this is evidence for. When we write the
  "Main Requirement Section", searching `REQ-2` returns every file that proves
  requirement 2. This is the part that will save hours in week four.

Keep the text to one line. The reasoning goes in the runbook, not the comment.
If it needs a paragraph, write the paragraph in `docs/runbooks/` and have the
marker point at it.

### Topic registry

Add a row when you invent a tag. Do not invent a second tag for something that
already has one.

| Tag | Covers |
|---|---|
| `T15-BE-WSGI` | gunicorn, workers, binds, the WSGI boundary |
| `T15-BE-NGINX` | reverse proxy config, SPA fallback, static/media locations |
| `T15-BE-HOSTHDR` | `Host` / `X-Forwarded-*` handling and `ALLOWED_HOSTS` |
| `T15-BE-MIGRATE` | schema migrations: where they run, in what order |
| `T15-BE-STATIC` | `collectstatic`, whitenoise |
| `T15-BE-MEDIA` | uploaded product images, local disk vs S3 |
| `T15-BE-DB` | database connection, driver, dev-vs-prod backing service |
| `T15-BE-SECRETS` | how a secret reaches a process without being committed |
| `T15-BE-HEALTH` | `/healthz/`, `/readyz/`, `/api/version/` and their probes |
| `T15-BE-TEST` | test harness structure and tooling decisions |
| `T15-FE-BUILD` | Vite build, bundle output, artifact promotion |
| `T15-FE-CONFIG` | runtime `config.js` injection |
| `T15-INFRA-NET` | VPC, subnets, routing, security groups |
| `T15-INFRA-IAM` | roles, instance profiles, `LabRole` constraints |
| `T15-CI` | Jenkins stages, agents, credentials |
| `T15-CD` | deployment, promotion, rollback |
| `T15-OPS` | monitoring, alerting, log aggregation |

### Requirement registry

| Tag | Requirement |
|---|---|
| `REQ-1` | Cloud integration |
| `REQ-2` | Containerised services |
| `REQ-3` | Continuous integration |
| `REQ-4` | Continuous deployment |
| `REQ-5` | Testing framework |
| `REQ-6` | Automation tool (Jenkins) |
| `REQ-7` | Configuration management (Ansible) |
| `REQ-8` | Automated alerting |
| `REQ-9` | Orchestration |
| `ADV-1` | Infrastructure as Code (CloudFormation) |
| `ADV-2` | Monitoring and alerting |
| `ADV-3` | Advanced deployment strategy |
| `ADV-4` | Additional enhancements |

A marker may carry more than one requirement tag: `[T15-BE-MEDIA][REQ-9][ADV-1]`.

---

## 3. Commits

Conventional Commits. Imperative mood, no trailing full stop, subject under 72
characters.

```
type(scope): subject
```

**Types:** `feat`, `fix`, `test`, `docs`, `chore`, `refactor`, `ci`

**Scopes:** `repo`, `be`, `fe`, `docker`, `compose`, `ansible`, `infra`,
`jenkins`, `docs`

Examples:

```
test(be): add unit tests for payment gateway and money helpers
feat(docker): add backend image with non-root runtime and health check
docs(runbook): add Plan B single-instance EC2 guide
fix(ansible): set source_dest_check false on the NAT instance
```

One logical change per commit. If the subject needs an "and", it is probably
two commits.

---

## 4. Branches and PRs

Branch protection is on — `main` takes merges through a PR only.

```
<type>/<short-slug>        e.g. test/be-payment-unit, feat/docker-backend
```

Fill in `.github/PULL_REQUEST_TEMPLATE.md`. In **Changes in this PR**, list the
marker tags you added, so a reviewer can jump straight to the decisions rather
than reading the whole diff.
