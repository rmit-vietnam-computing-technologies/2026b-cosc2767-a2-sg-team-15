# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every case. The failure modes covered are
#   the ones named in the assignment brief: misconfiguration that only shows
#   up in a deployed environment, and the ALLOWED_HOSTS interaction with a
#   load balancer health check. References:
#   Django settings and ALLOWED_HOSTS, https://docs.djangoproject.com/en/5.1/ref/settings/#allowed-hosts
#   django-environ, https://django-environ.readthedocs.io/en/latest/

"""
[T15-BE-TEST][REQ-5] Configuration-failure tests.

The brief asks for tests covering "misconfiguration that only shows up in a
deployed environment". This module is that. Nothing here is about business
logic; every case is a way a correct build fails on a wrong environment, and
each one has cost somebody a deployment:

**Boot guards.** ``config.settings.prod`` refuses to start on a default
``SECRET_KEY`` or an empty ``ALLOWED_HOSTS``. These run in a real subprocess
rather than by re-importing the module, because the property under test is
that *the process does not come up* — which is what makes the health check
never pass, the rollout halt, and the previous version keep serving. An
import-level test would assert something weaker and would also have to fight
whatever is already in ``sys.modules``.

**The host header.** A load balancer health check arrives with a ``Host`` of
the instance's private IP. If that is not in ``ALLOWED_HOSTS``, Django answers
400, the target group marks a healthy instance unhealthy, and the deployment
fails in a way that looks like the application is broken. This is trap 7 in
the brief and it is worth its own tests.

**Readiness.** ``/healthz/`` and ``/readyz/`` answer different questions and
must fail differently. A probe wired to the wrong one either restarts healthy
instances or routes traffic to a broken one.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.db.utils import OperationalError

# server/ — the directory manage.py lives in, and the working directory the
# subprocess boots from.
SERVER_DIR = Path(__file__).resolve().parents[2]

DEFAULT_SECRET_KEY = "dev-only-insecure-key-change-me-before-you-deploy-anywhere"
REAL_SECRET_KEY = "t3st-only-but-not-the-shipped-default-0123456789abcdef"

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Booting a settings module in a clean process
# ---------------------------------------------------------------------------


def _boot(settings_module="config.settings.prod", **overrides):
    """Start Django in a subprocess and report what happened.

    Returns the CompletedProcess. On a successful boot the child prints a JSON
    object of the settings the caller asked about, so one process start can
    answer several assertions instead of one.

    The environment is built from scratch with ``env -i`` semantics — only
    PATH, HOME and what the caller passes. That matters because ``base.py``
    reads ``server/.env`` when it exists, and django-environ's ``read_env``
    uses setdefault semantics: anything already in the environment wins, so
    setting a variable explicitly here makes the test independent of whatever
    happens to be in a developer's local ``.env``.
    """
    probe = (
        "import django, json; django.setup();"
        "from django.conf import settings;"
        "print(json.dumps({"
        "  'ALLOWED_HOSTS': settings.ALLOWED_HOSTS,"
        "  'DEBUG': settings.DEBUG,"
        "  'APP_VERSION': settings.APP_VERSION,"
        "  'GIT_COMMIT': settings.GIT_COMMIT,"
        "  'USE_X_FORWARDED_HOST': settings.USE_X_FORWARDED_HOST,"
        "  'SECURE_PROXY_SSL_HEADER': list(settings.SECURE_PROXY_SSL_HEADER or ()),"
        "  'RENDERERS': list(settings.REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES']),"
        "}))"
    )
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", "/tmp"),
        "DJANGO_SETTINGS_MODULE": settings_module,
        **{key: str(value) for key, value in overrides.items()},
    }
    return subprocess.run(
        [sys.executable, "-c", probe],
        cwd=SERVER_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _booted_settings(result):
    assert result.returncode == 0, f"boot failed:\n{result.stderr}"
    return json.loads(result.stdout)


# ===========================================================================
# Boot guards — the process must refuse to start
# ===========================================================================


@pytest.mark.slow
def test_production_refuses_to_boot_with_the_shipped_secret_key():
    """[REQ-5] The dev key is public. Booting on it is a security incident.

    Refusing to start is the correct behaviour rather than an inconvenience:
    a process that never becomes healthy cannot be rolled into the load
    balancer, so the misconfiguration is contained to a failed deployment
    instead of becoming a running one.
    """
    result = _boot(SECRET_KEY=DEFAULT_SECRET_KEY, ALLOWED_HOSTS="store.example.com")

    assert result.returncode != 0
    assert "RuntimeError" in result.stderr
    assert "SECRET_KEY" in result.stderr


@pytest.mark.slow
def test_production_refuses_to_boot_without_allowed_hosts():
    """[REQ-5] An empty value counts as unset.

    ``env.list`` returns ``[]`` for both a missing variable and an empty
    string, so ``ALLOWED_HOSTS=`` in a compose file or a systemd unit is
    caught the same way a forgotten one is. Without the guard this boots with
    ``ALLOWED_HOSTS = []`` and rejects every request with 400, including the
    health check.
    """
    result = _boot(SECRET_KEY=REAL_SECRET_KEY, ALLOWED_HOSTS="")

    assert result.returncode != 0
    assert "RuntimeError" in result.stderr
    assert "ALLOWED_HOSTS" in result.stderr


@pytest.mark.slow
def test_production_boots_when_both_are_supplied():
    """The positive control.

    Without this, the two tests above would pass just as happily against a
    settings module that refused to start for some entirely different reason.
    """
    result = _boot(
        SECRET_KEY=REAL_SECRET_KEY, ALLOWED_HOSTS="store.example.com,10.0.1.42"
    )

    settings = _booted_settings(result)
    assert settings["ALLOWED_HOSTS"] == ["store.example.com", "10.0.1.42"]
    assert settings["DEBUG"] is False


@pytest.mark.slow
def test_development_settings_have_no_such_guard():
    """The diff between dev and prod is the whole lesson.

    dev.py boots on the shipped key with ``ALLOWED_HOSTS = ["*"]``, which is
    exactly what makes it convenient on a laptop and unacceptable anywhere
    else. Asserting it here means the two modules cannot quietly converge.
    """
    result = _boot(settings_module="config.settings.dev", SECRET_KEY=DEFAULT_SECRET_KEY)

    settings = _booted_settings(result)
    assert settings["ALLOWED_HOSTS"] == ["*"]
    assert settings["DEBUG"] is True


@pytest.mark.slow
def test_production_is_configured_for_a_load_balancer():
    """[T15-BE-HOSTHDR] An ALB terminates TLS and forwards plain HTTP.

    Without these two, Django believes every request is insecure:
    ``SECURE_SSL_REDIRECT`` loops forever and ``build_absolute_uri`` emits
    ``http://`` links into password-reset emails.
    """
    settings = _booted_settings(
        _boot(SECRET_KEY=REAL_SECRET_KEY, ALLOWED_HOSTS="store.example.com")
    )

    assert settings["USE_X_FORWARDED_HOST"] is True
    assert settings["SECURE_PROXY_SSL_HEADER"] == ["HTTP_X_FORWARDED_PROTO", "https"]


@pytest.mark.slow
def test_production_does_not_expose_the_browsable_api():
    """The browsable API renders templates and reflects request data."""
    settings = _booted_settings(
        _boot(SECRET_KEY=REAL_SECRET_KEY, ALLOWED_HOSTS="store.example.com")
    )

    assert settings["RENDERERS"] == ["rest_framework.renderers.JSONRenderer"]


@pytest.mark.slow
def test_build_metadata_comes_from_the_environment():
    """[T15-BE-HEALTH][ADV-3] What ``/api/version/`` will report after a deploy.

    These two variables are how a blue/green cutover is verified from outside
    the instance, so they have to arrive from the environment rather than
    being baked into an image.
    """
    settings = _booted_settings(
        _boot(
            SECRET_KEY=REAL_SECRET_KEY,
            ALLOWED_HOSTS="store.example.com",
            APP_VERSION="2.4.1",
            GIT_COMMIT="a71dea9",
        )
    )

    assert settings["APP_VERSION"] == "2.4.1"
    assert settings["GIT_COMMIT"] == "a71dea9"


# ===========================================================================
# The host header — trap 7 in the brief
# ===========================================================================


def test_a_host_outside_allowed_hosts_is_rejected(api, settings):
    """[T15-BE-HOSTHDR][REQ-5] 400, before the request reaches a view.

    This is the single most common cause of a deployment that "works on the
    instance but not through the load balancer": curling localhost sends
    ``Host: localhost``, which is allowed, while the target group sends the
    private IP, which is not.
    """
    settings.ALLOWED_HOSTS = ["store.example.com"]

    response = api.get("/healthz/", HTTP_HOST="10.0.1.42")

    assert response.status_code == 400


def test_the_private_ip_health_check_passes_once_the_host_is_allowed(api, settings):
    """The fix, asserted rather than described.

    An instance's private IP is not known until it exists, which is why the
    Ansible work templates this value from instance metadata instead of
    anyone editing it by hand at the start of every Learner Lab session.
    """
    settings.ALLOWED_HOSTS = ["store.example.com", "10.0.1.42"]

    response = api.get("/healthz/", HTTP_HOST="10.0.1.42")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_rejection_is_indiscriminate(api, settings):
    """Every path fails, not only the probe.

    Worth pinning because the symptom is confusing: the target group reports
    unhealthy instances while an engineer SSH'd into the box sees a perfectly
    working site, because they are sending a different Host header.
    """
    settings.ALLOWED_HOSTS = ["store.example.com"]

    for path in ("/healthz/", "/readyz/", "/api/version/", "/api/products/"):
        assert api.get(path, HTTP_HOST="10.0.1.42").status_code == 400, path


def test_a_wildcard_subdomain_entry_matches(api, settings):
    """``.example.com`` covers the domain and every subdomain of it."""
    settings.ALLOWED_HOSTS = [".example.com"]

    assert api.get("/healthz/", HTTP_HOST="store.example.com").status_code == 200
    assert api.get("/healthz/", HTTP_HOST="example.com").status_code == 200
    assert api.get("/healthz/", HTTP_HOST="store.example.org").status_code == 400


# ===========================================================================
# Liveness and readiness
# ===========================================================================


def test_healthz_touches_nothing(api, db, django_assert_num_queries):
    """[T15-BE-HEALTH] Liveness must not depend on the database.

    A liveness probe that checks its dependencies restarts a perfectly
    healthy application server because the database was briefly slow, turning
    a small outage into a restart loop. Asserting zero queries is how that
    stays true through a later refactor.

    The ``db`` fixture is here for the query counter, which needs a
    connection to count against — not because the endpoint uses one. That it
    issues none while a connection is sitting available is exactly the point.
    """
    with django_assert_num_queries(0):
        response = api.get("/healthz/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_healthy_when_dependencies_are_up(api, db):
    response = api.get("/readyz/")

    assert response.status_code == 200
    assert response.json() == {"database": "ok", "storage": "ok"}


def test_readyz_returns_503_when_the_database_is_unreachable(api, db, monkeypatch):
    """[T15-BE-HEALTH][REQ-5] Failing readiness takes the instance out of
    rotation without killing it, so it can recover and rejoin.

    The cursor is made to raise the exception a real outage produces, rather
    than the database actually being stopped — which would take the test
    database with it and fail the rest of the run for the wrong reason.
    """

    class _BrokenConnections:
        def __getitem__(self, alias):
            raise OperationalError("could not connect to server")

    monkeypatch.setattr("apps.core.views.connections", _BrokenConnections())

    response = api.get("/readyz/")

    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"


def test_healthz_stays_up_while_readyz_is_down(api, db, monkeypatch):
    """[REQ-5] The two probes must disagree, and this is the state where it matters.

    A load balancer probing ``/healthz/`` keeps sending traffic to an
    instance that cannot serve it; one probing ``/readyz/`` for liveness
    kills instances it should merely have drained. The distinction only earns
    its keep if the endpoints genuinely behave differently under failure.
    """

    class _BrokenConnections:
        def __getitem__(self, alias):
            raise OperationalError("could not connect to server")

    monkeypatch.setattr("apps.core.views.connections", _BrokenConnections())

    assert api.get("/readyz/").status_code == 503
    assert api.get("/healthz/").status_code == 200


def test_readyz_returns_503_when_storage_is_unreachable(api, db, monkeypatch):
    """The S3 case. Once media moves off local disk, storage can fail alone."""

    def _explode(*args, **kwargs):
        raise OSError("storage backend unreachable")

    monkeypatch.setattr("apps.core.views.default_storage.exists", _explode)

    response = api.get("/readyz/")

    assert response.status_code == 503
    body = response.json()
    assert body["storage"] == "unavailable"
    # The database is fine, and the body says so — which is the difference
    # between a probe that tells you where to look and one that just says no.
    assert body["database"] == "ok"


def test_the_probes_need_no_credentials(api, db, settings):
    """Both sit outside /api/ and outside the authentication stack.

    A probe that required a token would fail the moment the token expired,
    and the instance would be removed from service for a reason that has
    nothing to do with its health.
    """
    settings.ALLOWED_HOSTS = ["testserver"]

    assert api.get("/healthz/").status_code == 200
    assert api.get("/readyz/").status_code == 200


# ===========================================================================
# Which build is running
# ===========================================================================


def test_version_endpoint_reports_the_running_build(api, settings):
    """[ADV-3] How a blue/green cutover is verified from outside the box."""
    settings.APP_VERSION = "2.4.1"
    settings.GIT_COMMIT = "a71dea9"

    response = api.get("/api/version/")

    assert response.status_code == 200
    assert response.json() == {"version": "2.4.1", "commit": "a71dea9"}


def test_version_endpoint_needs_no_credentials(api):
    """It has to be readable through the load balancer by a deploy script."""
    assert api.get("/api/version/").status_code == 200


def test_public_config_exposes_the_tax_rate_the_server_actually_uses(api, settings):
    """The SPA reads store rules at runtime rather than baking them into a bundle.

    A tax rate compiled into the frontend is a rate that needs a rebuild to
    change, and a rebuild per environment is the anti-pattern the runtime
    config design exists to avoid.
    """
    settings.SALES_TAX_RATE = 0.07

    response = api.get("/api/config/")

    assert response.status_code == 200
    assert response.json()["sales_tax_rate"] == 0.07
