<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 08/09/2026
Last modified: 09/09/2026
Acknowledgement: Written with help from Claude (Anthropic). All screenshots are mine.
-->

# Backend evidence

Screenshots from deploying the backend by hand (Plans A to E in the upstream
README) and from getting the test suites running. The `REQ-*` ones are what
I'd put in the report body; the per-plan folders are appendix material.

| File | What it shows |
|---|---|
| `REQ-1-01-store-live-on-ec2.png` | Store served from one EC2 instance (Plan B) |
| `REQ-1-02-store-live-on-split-tier.png` | Web and API on separate instances via Ansible (Plan C) |
| `REQ-2-02-store-live-on-compose.png` | All three tiers as containers under Compose (Plan E) |
| `REQ-2-03-two-instances-with-s3.png` | Two API containers on two instances sharing an S3 media bucket (Plan D) |
| `REQ-3-01-suite-green-in-ci-overlay.png` | Backend suite passing inside the API image via `compose.ci.yaml` |
| `REQ-5-02-suite-green-with-coverage-gate.png` | Unit + integration with the `--cov-fail-under` gate |
| `REQ-5-03/04/05-smoke-*.png` | Smoke suite green against EC2, the split tier, and the Compose stack |
| `plan-a/` to `plan-e/` | Step-by-step captures from each manual deploy |

What the tests actually cover is in `webapp/server/tests/README.md`.
