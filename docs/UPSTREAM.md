<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 02/09/2026
Last modified: 02/09/2026
Acknowledgement: Application source is Tom Huynh's COSC2767-RMIT-Store-Django-Vue.
-->

# Vendored application

## What was imported

| | |
|---|---|
| Source | <https://github.com/TomHuynhSG/COSC2767-RMIT-Store-Django-Vue> |
| Commit | `a71dea9151e77af06dabad7efd5255febb20fd60` |
| Short SHA | `a71dea9` |
| Commit date | 2026-08-13 |
| Imported on | 02/09/2026 |
| Imported by | Vo Hoang Khanh (s3926310) |

Imported as a **plain copy with upstream git history removed**, not a submodule
and not a subtree. Reasons, in order of weight:

1. The brief requires the supplied application to be *present* in the
   submission. A submodule clones as an empty directory for anyone without
   network access to the upstream at marking time.
2. The header rule ("not required on the supplied application files you did not
   touch") only distinguishes our work from Tom's if both live in one tree.
3. A pinned SHA recorded here gives the same reproducibility a submodule would,
   at the cost of one line of documentation instead of a second repository.

This is a **submission constraint, not general best practice**. In industry you
would consume a third party's application as a container image or a package
from a registry, pinned by digest, and never copy its source into your own
repository. See `docs/reflection-notes.md` — this is worth a paragraph in the
Self Evaluation section.

## Layout

| Path | Origin | Header required |
|---|---|---|
| `client/` | Upstream, verbatim | No — unless we edit a file |
| `server/` | Upstream, verbatim | No — unless we edit a file |
| `screenshots/` | Upstream, verbatim | No |
| `UPSTREAM-README.md` | Upstream `README.md`, verbatim | No |
| `server/tests/` | **Ours** | Yes |
| `docs/` | **Ours** | Yes |
| `deploy/` | **Ours** | Yes |
| `infra/` | **Ours** | Yes |
| `.github/` | **Ours** | Yes |

`UPSTREAM-README.md` stays at the repository root rather than under `docs/` so
its relative links into `screenshots/` still resolve. Do not edit it — it is
Tom's reference document and we cite it, we do not maintain it.

## Rule for modifying an upstream file

Default is **don't**. The brief is explicit that the pipeline is the
deliverable, not the application. If a change is genuinely unavoidable:

1. Add the standard header from `docs/CONVENTIONS.md`.
2. Add a marker at the exact line explaining why the change was necessary.
3. Add a row to the table below in the same commit.
4. Say so in the PR description.

### Modifications to upstream files

| File | Change | Why | Commit |
|---|---|---|---|
| _(none yet)_ | | | |

If this table is still empty at submission, that is a good sign, and it is
worth saying so in the report.

## Re-importing

Only if Tom pushes a fix we need. Diff first, never overwrite blind:

```bash
git clone https://github.com/TomHuynhSG/COSC2767-RMIT-Store-Django-Vue.git /tmp/rmit-upstream
diff -ru --exclude=.git --exclude=node_modules --exclude=.venv \
     --exclude=media --exclude=dist --exclude=__pycache__ \
     /tmp/rmit-upstream/server ./server
```

Anything the diff reports that is not in the modifications table above is drift
and needs explaining.
