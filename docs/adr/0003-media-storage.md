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
records. Drafted with Claude (Anthropic) in a guided session after a team
discussion on 06/09/2026; the decision is the team's. Reference:
assignment brief, "Why this stack makes the deployment problem interesting"
item 4; django-storages S3 backend documentation,
https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html
-->

# ADR 0003 — Where uploaded product images live

**Status:** Accepted, 07/09/2026
**Tags:** `[REQ-2]` `[REQ-9]` `[ADV-1]` `[T15-BE-MEDIA]`

## Context

By default Django writes uploaded product images to `server/media/` on the
local disk of whichever process handled the upload. The brief calls this
out as a deliberate trap:

> The moment you run a second replica, images uploaded to one container 404
> from the other. Fixing this properly, with shared object storage, is part
> of the work.

The failure looks random from a browser: an image appears or disappears
depending on which replica the load balancer picks. Nothing in a log says
why.

Plan B and Plan C both serve media off local disk through nginx, and both
work, because each runs exactly one API process. The question raised during
the Plan C work was whether to move to S3 immediately, since the pieces —
`django-storages` and `boto3` are already in `requirements.txt` — are
cheap to wire up.

## Decision

**Local disk through Plan C. S3 from Plan F, in the same step that
introduces containers and a second replica.**

The trigger is the second replica, not the passage of time. Plan C has one
API instance; local disk is the *correct* choice for that topology, and
replacing it early would add an AWS dependency to a deployment that
otherwise needs none, without fixing a problem the deployment has.

Plan F is where the problem appears, so Plan F is where it is fixed:

1. A bucket and an instance role, both defined in CloudFormation (ADV-1),
   so the API tier obtains credentials from IMDS and no key is ever in a
   file.
2. `STORAGES["default"]` in `config/settings/prod.py` set to the S3 backend
   **when `MEDIA_BUCKET` is present in the environment**, and unchanged
   otherwise. Plan C keeps working with no code branch at deploy time.
3. `MEDIA_BUCKET` added to the environment template. The `/media/`
   location in both nginx configs becomes unused and is removed along with
   the media-directory and home-directory-traversal tasks in the api role.
4. The smoke test `test_product_image_urls_point_at_this_deployment`
   rewritten to assert the URL is absolute *and fetchable*, since image
   URLs will no longer be on the deployment's host. That test already
   checks the pointer rather than the thing — it passed once while the
   storefront showed no images — and this is the forcing function to fix
   it.

Static files (`collectstatic` output: admin CSS, browsable-API assets) do
**not** move. They are build artefacts, identical on every replica, and
whitenoise serves them from the container. Only user uploads are state.

## Consequences

**Good**

- The API tier becomes fully stateless once this and ADR 0002 are both in
  place. Replicas are disposable; scaling and rollback stop being data
  questions.
- Three role tasks disappear. `chmod 0711` on the application user's home
  — the cause of the `403 /media/` row in the Plan B troubleshooting table
  — is one of them. Moving state off the instance removes configuration
  rather than adding it, which is worth saying in the report.
- A CDN in front of the bucket (ADV-4) becomes a one-line change rather
  than an architecture change.

**Costs and risks**

- The Learner Lab does not allow custom IAM roles. The preexisting
  `LabRole` and its instance profile must cover `s3:PutObject` and
  `s3:GetObject` on the bucket, and must be attachable to the API
  instances. **Confirm this before Plan F depends on it**; if it is
  blocked, the fallback is a scoped access key in Secrets Manager, which is
  worse but workable.
- `seed_demo` uploads 47 product photos. Against S3 that is 47 network
  writes rather than 47 file copies, and re-running it is either 47
  redundant `PUT`s or needs an existence check. The marker-file guard added
  in Plan C already prevents the re-run.
- Objects need public-read (or a CloudFront origin access identity) for
  `<img>` tags to load them. Plain image tags are not subject to CORS, so
  no CORS configuration is needed on the bucket.
- `/readyz/` checks storage. After the change it is checking S3
  reachability, so a bucket permission error surfaces as an unready
  instance rather than as broken images. That is better, and it is a
  behaviour change to know about when reading the readiness probe.

## Alternatives considered

**S3 now, in Plan C.** The application half is portable and would carry
into Plan F unchanged. Rejected because the infrastructure half — bucket,
role, group vars, removed tasks — is rebuilt in Plan F anyway, and because
changing the storage backend after Plan C's evidence was captured means
every screenshot is against a topology that no longer exists. The
application-side settings block may still be landed early, guarded on the
environment variable, without changing Plan C's behaviour.

**A shared filesystem (EFS) mounted on every replica.** Solves the
consistency problem with no code change. Rejected: it keeps the
filesystem-as-storage model the brief is steering away from, adds a mount
to every container, and costs more than S3 for a workload that is
write-once, read-many.

**Serving media through Django (`MEDIA_URL` handled by the app).** Never an
option in production — Django refuses under production settings, and it
would put image bytes through gunicorn workers.

## Related

- `docs/adr/0002-database-topology.md` — the same principle for the
  database.
- `deploy/plan-c/roles/api/tasks/main.yml` — the three tasks this removes.
- `server/tests/smoke/test_deployment.py` — the test this rewrites.
