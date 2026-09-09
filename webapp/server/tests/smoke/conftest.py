# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 09/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every fixture. Reference:
#   requests documentation, https://requests.readthedocs.io/en/latest/

"""
Fixtures for the deployment smoke suite.

    SMOKE_BASE_URL=http://<host>   pytest -m smoke --no-cov

Always --no-cov: these tests run no local code and would overwrite
coverage.xml with ~0%. Optional variables, each skipping its checks when unset:
SMOKE_SPA_BASE_URL (frontend origin), SMOKE_EXPECTED_COMMIT and
SMOKE_EXPECTED_VERSION (what /api/version/ must report), SMOKE_MEMBER_EMAIL
and SMOKE_MEMBER_PASSWORD (authenticated checks), SMOKE_TIMEOUT (10s),
SMOKE_WAIT (60s for the deployment to answer).
"""

import os
import time

import pytest
import requests

pytestmark = pytest.mark.smoke


def _env(name, default=None):
    value = os.environ.get(name, "")
    return value.strip() or default


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url():
    """The API origin, or skip the whole suite.

    Skip rather than fail. A developer running the full suite on a laptop has
    nothing deployed, and a red build for that is noise — which is why
    ``-m "not smoke"`` is already the default in pytest.ini. In the pipeline
    the variable is always set, so a skip there means the stage was
    misconfigured and is worth reading as a failure.
    """
    url = _env("SMOKE_BASE_URL")
    if not url:
        pytest.skip("SMOKE_BASE_URL is not set")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def spa_base_url():
    """The frontend origin.

    Separate from the API origin because the two are only the same thing
    behind a single nginx. Once the tiers are split they are different hosts,
    and a suite that assumed otherwise would silently test the API twice.
    """
    url = _env("SMOKE_SPA_BASE_URL")
    if not url:
        pytest.skip("SMOKE_SPA_BASE_URL is not set")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def timeout():
    return float(_env("SMOKE_TIMEOUT", "10"))


# ---------------------------------------------------------------------------
# Waiting for the deployment
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _wait_for_liveness(request, timeout):
    """Poll /healthz/ until the deployment answers, then let the suite run.

    A deploy script runs this immediately after starting containers, and
    gunicorn takes a second or two to bind. Without the wait the first
    assertion loses a race and the pipeline reports a failed deployment that
    actually succeeded — the classic flaky post-deploy check.

    Liveness, not readiness, is the right thing to wait on here: it answers
    as soon as the process can serve, and the readiness test that follows is
    then a real assertion about dependencies rather than a second wait.
    """
    url = _env("SMOKE_BASE_URL")
    if not url:
        return

    deadline_seconds = float(_env("SMOKE_WAIT", "60"))
    deadline = time.monotonic() + deadline_seconds
    last_error = None

    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{url.rstrip('/')}/healthz/", timeout=timeout)
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}"
        except requests.RequestException as exc:
            # The full repr nests urllib3's MaxRetryError inside requests'
            # ConnectionError and runs to three lines of quoted punctuation.
            # The class name says everything a reader needs: refused, timed
            # out, or DNS.
            last_error = type(exc).__name__
        time.sleep(2)

    pytest.fail(
        f"{url} did not answer /healthz/ within {deadline_seconds:.0f}s. "
        f"Last result: {last_error}. "
        "Is anything listening on that address? "
        "Set SMOKE_WAIT=5 to fail faster while working locally.",
        # Without this, one unreachable deployment prints this fixture's full
        # source and traceback once per test -- twenty-odd screens of
        # identical output for a single root cause, in a CI log somebody has
        # to scroll through at three in the morning. The message is the whole
        # diagnosis; the traceback adds nothing.
        pytrace=False,
    )


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def http(timeout):
    """A session that never follows redirects silently and always times out.

    ``allow_redirects=False`` is deliberate. A 301 from a missing trailing
    slash, or a redirect loop from ``SECURE_SSL_REDIRECT`` set while the
    instance is still on plain HTTP, are both real deployment faults; a
    client that quietly followed them would report success.

    A request with no timeout can hang the pipeline indefinitely, which is
    worse than a failed build.
    """

    class _Client:
        def __init__(self):
            self._session = requests.Session()
            self._session.headers["User-Agent"] = "rmit-store-smoke/1.0"

        def get(self, url, **kwargs):
            kwargs.setdefault("timeout", timeout)
            kwargs.setdefault("allow_redirects", False)
            return self._session.get(url, **kwargs)

        def post(self, url, **kwargs):
            kwargs.setdefault("timeout", timeout)
            kwargs.setdefault("allow_redirects", False)
            return self._session.post(url, **kwargs)

    client = _Client()
    yield client
    client._session.close()


@pytest.fixture(scope="session")
def member_token(http, base_url):
    """An access token, or skip.

    Opt-in via SMOKE_MEMBER_EMAIL and SMOKE_MEMBER_PASSWORD, because the
    authenticated checks are the only ones that are not purely read-only and
    the credentials differ per environment.
    """
    email = _env("SMOKE_MEMBER_EMAIL")
    password = _env("SMOKE_MEMBER_PASSWORD")
    if not (email and password):
        pytest.skip("SMOKE_MEMBER_EMAIL / SMOKE_MEMBER_PASSWORD are not set")

    response = http.post(
        f"{base_url}/api/auth/login/",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, (
        f"smoke credentials rejected: HTTP {response.status_code} {response.text[:200]}"
    )
    return response.json()["access"]


@pytest.fixture(scope="session")
def auth(member_token):
    return {"Authorization": f"Bearer {member_token}"}