# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 09/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every case. The runtime-configuration
#   contract is documented in client/public/config.js and in the nginx
#   section of the upstream README. Reference:
#   requests documentation, https://requests.readthedocs.io/en/latest/

"""
Deployment smoke tests: the frontend tier.

Gated on its own ``SMOKE_SPA_BASE_URL`` because the tiers are only the same
origin behind one nginx. Unset, this module skips.
"""

import pytest

pytestmark = pytest.mark.smoke


def test_the_spa_is_served_at_the_root(http, spa_base_url):
    """Something is serving index.html.

    A 403 here is almost always nginx pointed at a directory that does not
    contain the build; a 404 is a build that never got copied.
    """
    response = http.get(f"{spa_base_url}/")

    assert response.status_code == 200, response.text[:300]
    assert "text/html" in response.headers.get("Content-Type", "")


def test_a_client_route_falls_back_to_the_spa(http, spa_base_url):
    """The single most common frontend deployment fault.

    ``/shop`` is a Vue Router path, not a file on disk. Navigating to it from
    inside the application works because the router handles it in the
    browser; refreshing the page asks the web server for a file that does not
    exist. Without ``try_files $uri /index.html`` the user gets a 404 on
    reload — and only on reload, which is exactly the sort of bug that
    survives manual testing.
    """
    response = http.get(f"{spa_base_url}/shop")

    assert response.status_code == 200, (
        "/shop did not fall back to index.html — the SPA fallback is missing "
        "from the web server config"
    )
    assert "text/html" in response.headers.get("Content-Type", "")


def test_a_deep_client_route_also_falls_back(http, spa_base_url):
    """The fallback has to cover nested paths, not just one level."""
    response = http.get(f"{spa_base_url}/account/orders")

    assert response.status_code == 200


def test_the_runtime_config_is_served_unhashed(http, spa_base_url):
    """The file that makes one artifact promotable.

    ``config.js`` is copied from ``public/`` into ``dist/`` unchanged and
    unhashed, so it sits next to index.html and can be replaced per
    environment without rebuilding. If this 404s, the bundle will fall back
    to whatever default it was compiled with and the storefront will talk to
    the wrong API — or to none.
    """
    response = http.get(f"{spa_base_url}/config.js")

    assert response.status_code == 200, (
        "config.js is not being served — the SPA cannot discover the API"
    )
    assert "API_BASE_URL" in response.text


def test_the_runtime_config_does_not_point_at_localhost(http, spa_base_url):
    """The misconfiguration that only a browser sees.

    ``API_BASE_URL`` is read by the *browser*, not by the server. Left
    pointing at localhost it works perfectly for anyone testing on the
    instance itself and fails for every real visitor, whose browser resolves
    localhost to their own machine.

    A relative ``/api`` is correct and expected behind a single nginx, so it
    passes; an absolute localhost URL does not.
    """
    body = http.get(f"{spa_base_url}/config.js").text

    for wrong in ("localhost", "127.0.0.1"):
        assert wrong not in body, (
            f"config.js points at {wrong} — every visitor's browser will try "
            "to reach the API on their own machine"
        )


def test_the_bundle_is_reachable_from_index(http, spa_base_url):
    """index.html references a built asset, and that asset is served.

    Catches the half-copied deploy: index.html present, the hashed
    ``assets/`` directory missing, so the page loads white with a console
    full of 404s.
    """
    index = http.get(f"{spa_base_url}/").text

    marker = "/assets/"
    assert marker in index, "index.html references no built assets — is this the build?"

    start = index.index(marker)
    end = min(
        (index.index(quote, start) for quote in ('"', "'") if quote in index[start:]),
        default=-1,
    )
    asset_path = index[start:end]

    response = http.get(f"{spa_base_url}{asset_path}")
    assert response.status_code == 200, (
        f"{asset_path} is referenced by index.html but returns "
        f"{response.status_code} — the build was only partly copied"
    )
