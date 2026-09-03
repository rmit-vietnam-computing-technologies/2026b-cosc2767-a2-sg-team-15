# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every case. The checks follow the
#   "Verifying a deployment" section of the upstream README and the endpoint
#   table in the assignment brief. References:
#   requests documentation, https://requests.readthedocs.io/en/latest/
#   Django deployment checklist, https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

"""
[T15-BE-TEST][REQ-5][REQ-4] Deployment smoke tests: the API tier.

The brief calls these "the cheapest and most valuable tests in the whole
pipeline", and it is right. Every assertion here fails for a reason no amount
of unit or integration testing can catch, because each one is a property of a
*deployment* rather than of the code: an environment variable that was never
set, a migration that did not run, a ``collectstatic`` that was skipped, a
database the container cannot reach, a proxy rewriting a header.

They are also what makes automated rollback possible. A deploy that passes
its smoke suite is promoted; one that fails is rolled back before it takes
traffic, and the previous version keeps serving. That decision needs a check
that runs in seconds against the real thing, from outside it.

Ordering is deliberate: liveness, then readiness, then identity, then
behaviour. A failure in the first group makes every later failure
meaningless, so read the first red line and ignore the rest.
"""

import os

import pytest

pytestmark = pytest.mark.smoke


def _env(name, default=None):
    return os.environ.get(name, "").strip() or default


# ===========================================================================
# Liveness and readiness
# ===========================================================================


def test_healthz_reports_alive(http, base_url):
    """The process is up and serving. Touches nothing else."""
    response = http.get(f"{base_url}/healthz/")

    assert response.status_code == 200, response.text[:300]
    assert response.json() == {"status": "ok"}


def test_readyz_reports_every_dependency_healthy(http, base_url):
    """[REQ-5] The database and storage, checked from inside the deployment.

    This is the assertion that catches a wrong ``DATABASE_URL``, a security
    group that does not allow 5432 from the API instance, an RDS endpoint
    that moved, or an S3 bucket the instance profile cannot reach. All four
    look identical from outside — the container is running and answering
    ``/healthz/`` perfectly — and all four mean the store is down.
    """
    response = http.get(f"{base_url}/readyz/")

    assert response.status_code == 200, (
        f"readiness failed: HTTP {response.status_code} {response.text[:300]}"
    )
    body = response.json()
    assert body["database"] == "ok"
    assert body["storage"] == "ok"


def test_the_probes_need_no_credentials(http, base_url):
    """A probe behind authentication fails the moment a token expires.

    The instance would then be pulled from service for a reason that has
    nothing to do with its health.
    """
    for path in ("/healthz/", "/readyz/"):
        assert http.get(f"{base_url}{path}").status_code == 200, path


# ===========================================================================
# Which build is this?
# ===========================================================================


def test_version_endpoint_answers(http, base_url):
    response = http.get(f"{base_url}/api/version/")

    assert response.status_code == 200
    body = response.json()
    assert body["version"]
    assert body["commit"]


def test_the_deployed_commit_is_the_one_we_shipped(http, base_url):
    """[REQ-4][ADV-3] The check that makes a promotion decision trustworthy.

    Without it, "the deploy succeeded" means only that a deploy command
    exited zero. An image that failed to pull, a Swarm service that rolled
    back on its own, or a stale task still serving all present as a healthy
    instance running the *previous* build — and this is the only assertion in
    the suite that tells them apart.

    Skipped when the variable is unset, so the suite still runs by hand
    against an environment whose commit you have not pinned.
    """
    expected = _env("SMOKE_EXPECTED_COMMIT")
    if not expected:
        pytest.skip("SMOKE_EXPECTED_COMMIT is not set")

    reported = http.get(f"{base_url}/api/version/").json()["commit"]

    assert reported == expected, (
        f"deployed commit is {reported!r}, expected {expected!r} — "
        "the rollout did not replace the running build"
    )


def test_the_deployed_version_is_the_one_we_shipped(http, base_url):
    expected = _env("SMOKE_EXPECTED_VERSION")
    if not expected:
        pytest.skip("SMOKE_EXPECTED_VERSION is not set")

    reported = http.get(f"{base_url}/api/version/").json()["version"]

    assert reported == expected


# ===========================================================================
# Did the deployment steps actually run?
# ===========================================================================


def test_static_files_were_collected(http, base_url):
    """[T15-BE-STATIC] ``collectstatic`` ran, and something is serving the result.

    The visible symptom of skipping it is the Django admin rendering as
    unstyled black-on-white text — cosmetic-looking, and in fact a missing
    deployment step. The admin's own stylesheet is the cheapest probe for it,
    and it works whether whitenoise or nginx is doing the serving.
    """
    response = http.get(f"{base_url}/static/admin/css/base.css")

    assert response.status_code == 200, (
        "collectstatic did not run, or nothing is serving /static/"
    )
    assert "css" in response.headers.get("Content-Type", "")


def test_the_admin_login_page_renders(http, base_url):
    """Reachable admin also proves templates and the session stack work."""
    response = http.get(f"{base_url}/admin/login/")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("Content-Type", "")


def test_the_api_docs_are_served(http, base_url):
    """/api/docs/ works before the frontend exists, so it is a useful early probe."""
    assert http.get(f"{base_url}/api/docs/").status_code == 200


def test_migrations_ran(http, base_url):
    """[T15-BE-MIGRATE] An empty schema answers 500, not 200.

    ``/readyz/`` opens a cursor and runs ``SELECT 1``, which succeeds against
    a database with no tables at all — so readiness does not prove ``migrate``
    ran. An endpoint that queries a real table does.
    """
    response = http.get(f"{base_url}/api/products/")

    assert response.status_code == 200, (
        f"HTTP {response.status_code} from /api/products/ — migrations may not have run"
    )


def test_the_catalogue_has_been_seeded(http, base_url):
    """Not a deployment failure, but a useless environment.

    A staging box with an empty catalogue passes every other check here and
    can demonstrate nothing. Separate from the migration check above so the
    two failures are told apart at a glance.
    """
    body = http.get(f"{base_url}/api/products/").json()

    assert body["count"] > 0, "the catalogue is empty — run seed_demo"


# ===========================================================================
# The misconfigurations that only appear once deployed
# ===========================================================================


def test_product_image_urls_point_at_this_deployment(http, base_url):
    """[T15-BE-MEDIA][REQ-5] The nastiest misconfiguration in the README.

    Image URLs are built at serialization time from the incoming request, so
    they are right only if the request arrived with the right ``Host``. Get
    the proxy headers wrong and every product image comes back as
    ``http://127.0.0.1:8000/media/...`` — which loads perfectly when you curl
    it from the instance and is a broken image in every browser on earth.

    Asserting against ``base_url`` rather than a hardcoded host makes this
    the same test on localhost, staging and production.
    """
    results = http.get(f"{base_url}/api/products/").json()["results"]
    with_images = [row for row in results if row.get("image_url")]

    if not with_images:
        pytest.skip("no seeded product carries an image")

    for row in with_images[:5]:
        assert row["image_url"].startswith(base_url), (
            f"{row['name']!r} has image_url {row['image_url']!r}, which is not on "
            f"{base_url} — check USE_X_FORWARDED_HOST and the proxy's Host header"
        )


def test_debug_mode_is_off(http, base_url):
    """[REQ-5] A deployment running with DEBUG=True leaks the whole application.

    Django's debug 404 lists every URL pattern in the project, and its 500
    renders local variables — including settings and, on a bad day, a
    database password. A production box serving those is a security incident,
    not a configuration preference.

    Detected by asking for a path that cannot exist and looking for the
    fingerprint of the debug page rather than the plain 404.

    The probe sits under /api/ deliberately. Behind nginx, an unknown path at
    the root is not a 404 at all — `try_files $uri $uri/ /index.html` treats
    it as a Vue route and answers 200 with the SPA, which is correct and is
    what test_a_client_route_falls_back_to_the_spa asserts. Only the prefixes
    nginx proxies reach Django, so a root-level probe tests the web server's
    fallback rather than Django's debug setting.
    """
    response = http.get(f"{base_url}/api/this-path-does-not-exist-smoke-probe/")

    assert response.status_code == 404, (
        f"expected 404 from Django, got {response.status_code} — is /api/ "
        "actually proxied to the application?"
    )
    body = response.text.lower()
    for fingerprint in ("using the urlconf defined in", "django settings module"):
        assert fingerprint not in body, (
            "the deployment is serving Django's debug pages — DEBUG is True"
        )


def test_the_api_answers_on_the_host_we_reach_it_by(http, base_url):
    """[T15-BE-HOSTHDR] ALLOWED_HOSTS accepts the name actually in use.

    A 400 here is the load-balancer trap: the instance is healthy, the
    application is fine, and every request through this hostname is refused
    before it reaches a view. Worth its own message because a 400 from
    ``/healthz/`` means exactly one thing.
    """
    response = http.get(f"{base_url}/healthz/")

    assert response.status_code != 400, (
        f"400 from /healthz/ — the host in {base_url} is missing from "
        "ALLOWED_HOSTS on the deployed instance"
    )


def test_the_probe_is_not_redirected(http, base_url):
    """``SECURE_SSL_REDIRECT=True`` on a plain-HTTP instance is a redirect loop.

    The client does not follow redirects, so this surfaces as a 301 rather
    than as a hang or a confusing timeout.
    """
    response = http.get(f"{base_url}/healthz/")

    assert response.status_code not in (301, 302, 307, 308), (
        f"/healthz/ redirected to {response.headers.get('Location')!r} — "
        "check SECURE_SSL_REDIRECT against the scheme this instance serves"
    )


# ===========================================================================
# Opt-in: the authenticated journey
# ===========================================================================


def test_a_member_can_authenticate(member_token):
    """The JWT round trip against a real deployment.

    Exercises the signing key, the clock and the auth stack end to end.
    Skipped unless credentials are supplied.
    """
    assert member_token


def test_a_declined_card_is_safe_to_fire_after_every_deploy(http, base_url, auth):
    """[REQ-5] A full checkout attempt that costs nothing and proves everything.

    The gateway is simulated, and a declined card leaves no order row and
    takes no stock. That is what makes this safe to run against production on
    every deployment — it exercises authentication, the serializer, the
    service layer, the transaction, the row lock and the write path, and then
    rolls all of it back.

    402 is the pass condition. A 500 means the write path is broken in a
    deployment that every read-only check above declared healthy.
    """
    products = http.get(f"{base_url}/api/products/").json()["results"]
    in_stock = next((row for row in products if row.get("in_stock")), None)
    if in_stock is None:
        pytest.skip("no seeded product is in stock")

    response = http.post(
        f"{base_url}/api/orders/",
        headers=auth,
        json={
            "items": [{"product": in_stock["id"], "quantity": 1}],
            "payment": {
                "number": "4000000000000002",
                "exp_month": 12,
                "exp_year": 2099,
                "cvc": "123",
                "name_on_card": "Smoke Test",
            },
        },
    )

    assert response.status_code == 402, (
        f"expected a decline, got HTTP {response.status_code}: {response.text[:300]}"
    )
    assert response.json()["decline_code"] == "card_declined"