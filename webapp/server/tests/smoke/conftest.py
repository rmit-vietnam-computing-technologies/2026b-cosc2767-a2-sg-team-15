# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified every fixture. Reference: pytest fixtures,
#   https://docs.pytest.org/en/stable/how-to/fixtures.html

"""Smoke fixtures.

    SMOKE_BASE_URL=http://<host> pytest -m smoke --no-cov

Optional: SMOKE_EXPECTED_COMMIT, SMOKE_MEMBER_EMAIL, SMOKE_MEMBER_PASSWORD,
SMOKE_TIMEOUT (10s), SMOKE_WAIT (60s).
"""

import os
import time

import pytest
import requests

pytestmark = pytest.mark.smoke


def _env(name, default=None):
    return os.environ.get(name, "").strip() or default


@pytest.fixture(scope="session")
def base_url():
    # Skip, not fail: a laptop with nothing deployed is not a red build.
    url = _env("SMOKE_BASE_URL")
    if not url:
        pytest.skip("SMOKE_BASE_URL is not set")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def timeout():
    return float(_env("SMOKE_TIMEOUT", "10"))


@pytest.fixture(scope="session", autouse=True)
def _wait_for_liveness(timeout):
    # gunicorn takes a moment to bind after a deploy; don't lose that race.
    url = _env("SMOKE_BASE_URL")
    if not url:
        return

    wait = float(_env("SMOKE_WAIT", "60"))
    deadline = time.monotonic() + wait
    last = None
    while time.monotonic() < deadline:
        try:
            if requests.get(f"{url.rstrip('/')}/healthz/", timeout=timeout).status_code == 200:
                return
            last = "not 200"
        except requests.RequestException as exc:
            last = type(exc).__name__
        time.sleep(2)

    pytest.fail(f"{url} did not answer /healthz/ within {wait:.0f}s ({last})", pytrace=False)


@pytest.fixture(scope="session")
def http(timeout):
    # Never follow redirects silently: a redirect loop is a deployment fault.
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
    email = _env("SMOKE_MEMBER_EMAIL")
    password = _env("SMOKE_MEMBER_PASSWORD")
    if not (email and password):
        pytest.skip("SMOKE_MEMBER_EMAIL / SMOKE_MEMBER_PASSWORD are not set")

    response = http.post(f"{base_url}/api/auth/login/", json={"email": email, "password": password})
    assert response.status_code == 200, f"login rejected: {response.status_code} {response.text[:200]}"
    return response.json()["access"]


@pytest.fixture(scope="session")
def auth(member_token):
    return {"Authorization": f"Bearer {member_token}"}