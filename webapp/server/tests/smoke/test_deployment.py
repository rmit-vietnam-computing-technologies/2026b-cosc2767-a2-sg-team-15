# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran it against
#   every topology from Plan B onward. Checks follow the upstream README's
#   "Verifying a deployment" section. Reference: requests documentation,
#   https://requests.readthedocs.io/en/latest/

"""Post-deploy checks over the network. Properties of a deployment, not of code."""

import os
import pytest

pytestmark = pytest.mark.smoke


def _env(name, default=None):
    return os.environ.get(name, "").strip() or default


def test_probes_pass_and_version_matches_the_shipped_commit(http, base_url):
    # Liveness, then readiness (database and storage), then which build is serving.
    alive = http.get(f"{base_url}/healthz/")
    assert alive.status_code == 200, alive.text[:300]
    assert alive.json() == {"status": "ok"}

    ready = http.get(f"{base_url}/readyz/")
    assert ready.status_code == 200, f"readiness failed: {ready.text[:300]}"
    assert ready.json() == {"database": "ok", "storage": "ok"}

    version = http.get(f"{base_url}/api/version/")
    assert version.status_code == 200
    reported = version.json()["commit"]
    expected = _env("SMOKE_EXPECTED_COMMIT")
    if expected:
        assert reported == expected, f"serving {reported!r}, deployed {expected!r}"
    else:
        assert reported


def test_declined_card_is_safe_to_fire_after_every_deploy(http, base_url, auth):
    # Exercises auth, serializer, service, transaction and the row lock, then rolls back.
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

    assert response.status_code == 402, f"HTTP {response.status_code}: {response.text[:300]}"
    assert response.json()["decline_code"] == "card_declined"
