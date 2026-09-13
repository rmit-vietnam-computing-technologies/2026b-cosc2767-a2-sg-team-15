<!--
RMIT University Vietnam
Course: COSC2767|COSC2805 Systems Deployment and Operations
Semester: 2026B
Assessment: Assignment 2
Author: Vo Hoang Khanh
ID: s3926310
Created  date: 08/09/2026
Last modified: 14/09/2026
Acknowledgement: Written with help from Claude (Anthropic). All screenshots are mine.
-->

# Backend evidence

Screenshots from building the backend pipeline. Top-level files are the
ones that go in the report body, one per point being made; the `plan-*`
folders are the manual deploys that came first and are appendix material.

## Pipeline

| File | Shows |
|---|---|
| `terraform-backend-apply.png` | Node, RDS, buckets and SSM parameters created from `terraform/backend` |
| `k3s-node-ready-via-ansible.png` | The playbook converging (`changed=0` on re-run) and the node `Ready` |
| `api-image-nginx-probes.png` | The API image: probes pass with a pod-IP Host, real requests still need `ALLOWED_HOSTS`, every process runs as `app`, the container exits when gunicorn dies |
| `compose-stack-nginx-api.png` | The local stack healthy through port 80 |
| `tests-twelve-green.png` | The 12-test suite inside the image against a throwaway Postgres, with coverage |
| `tests-smoke-in-stack.png` | Smoke checks from inside the Compose network |
| `k3s-staging-two-replicas-s3.png` | Two replicas, LoadBalancer on 8080, HPA reading, `readyz` ok, `image_url` on the staging bucket |
| `k3s-rollback-version-check.png` | A second build deployed, `rollout undo`, `/api/version/` back on the previous commit |
| `secrets-from-ssm.png` | The Secret's value equals the SSM parameter |
| `k3s-staging-and-prod-two-namespaces.png` | Both environments on one cluster, same image, ports 8080 and 80 |
| `metrics-endpoint-through-nginx.png` | django-prometheus metrics served through the container's nginx |

## Before the pipeline

| File | Shows |
|---|---|
| `store-live-single-ec2.png` | Plan B: everything on one instance |
| `store-live-split-tier.png` | Plan C: web and API on separate instances via Ansible |
| `store-live-compose.png` | Plan E: three containers under Compose |
| `two-instances-with-s3.png` | Plan D: two API containers on two instances sharing a bucket |
| `old-suite-green-in-ci-overlay.png` | The original 322-test suite passing inside the image, before the cut to 12 |
| `old-suite-green-with-coverage-gate.png` | The same suite with the coverage gate it used to have |
| `smoke-green-against-ec2.png`, `smoke-green-against-split-tier.png`, `smoke-23-green-in-compose-stack.png` | The original 23-check smoke suite against Plans B, C and E |
| `plan-a/` to `plan-e/` | Step-by-step captures from each manual deploy |

What the tests cover is in `webapp/server/tests/README.md`; how to reproduce
the pipeline is in `deploy/README.md`.