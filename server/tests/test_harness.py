# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every assertion. The note about
#   SETTINGS_MODULE reading as None under override_settings comes from
#   django.conf.UserSettingsHolder in the Django source. References:
#   Django database features, https://docs.djangoproject.com/en/5.1/ref/models/querysets/#select-for-update

"""
Does the harness itself work?

These assert the environment the rest of the suite assumes. If one fails, every
other failure in the run is probably downstream of it, so read them first.
"""

import os

import pytest
from django.conf import settings
from django.db import connection

from apps.accounts.models import Role


@pytest.mark.unit
def test_test_settings_are_active():
    """Guards against a stray DJANGO_SETTINGS_MODULE in someone's shell.

    Checks the environment variable and the values test.py sets, never
    ``settings.SETTINGS_MODULE``. The autouse media fixture assigns to the
    pytest-django ``settings`` fixture, which is implemented as
    ``override_settings``; that swaps in a ``UserSettingsHolder``, and Django
    hardcodes ``SETTINGS_MODULE = None`` on that class because the attribute is
    meaningless once settings are overridden. Asserting on it tests
    pytest-django's plumbing, not our configuration.
    """
    assert os.environ["DJANGO_SETTINGS_MODULE"] == "config.settings.test"

    # Values only test.py sets — a real check that the right module loaded.
    assert settings.USE_S3 is False
    assert "locmem" in settings.EMAIL_BACKEND
    assert settings.PASSWORD_HASHERS == [
        "django.contrib.auth.hashers.MD5PasswordHasher"
    ]
    assert all(
        rate is None
        for rate in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].values()
    ), "throttling must be off, or the authorisation matrix flakes at 20 req/min"


@pytest.mark.integration
def test_database_is_postgresql(db):
    """[T15-BE-DB][REQ-5] The suite runs on the same engine as production."""
    assert connection.vendor == "postgresql"


@pytest.mark.integration
def test_row_locking_is_available(db):
    """Why SQLite is not an option.

    ``apps.orders.services.create_order`` calls
    ``select_for_update(of=("self",))`` to hold a row lock while it checks stock
    and decrements it. SQLite has no ``SELECT ... FOR UPDATE``, so Django raises
    NotSupportedError rather than degrading — the checkout tests would not be
    less realistic, they would not run at all.

    ``of=(...)`` narrows the lock to the named table and needs
    ``has_select_for_update_of``, which is PostgreSQL and Oracle only.

    Asserting it here keeps the reason next to the check, instead of leaving it
    to be rediscovered by whoever tries to speed the suite up with SQLite.
    """
    assert connection.features.has_select_for_update
    assert connection.features.has_select_for_update_of


@pytest.mark.integration
def test_fixtures_build_all_four_roles(member, merchant, admin):
    """The role vocabulary the authorisation matrix depends on.

    Negative assertions matter as much as positive ones: a permission bug that
    grants a member merchant rights passes every test that only checks the
    merchant.
    """
    assert member.role == Role.MEMBER
    assert not member.is_store_admin
    assert not member.is_active_merchant

    assert admin.is_store_admin

    # Role, an existing Merchant record, and that record being active — all
    # three, which is what makes this worth a fixture.
    assert merchant.is_active_merchant


@pytest.mark.integration
def test_deactivated_merchant_is_not_active(deactivated_merchant):
    """[REQ-5] The case a role-only permission check waves through."""
    assert deactivated_merchant.role == Role.MERCHANT
    assert deactivated_merchant.merchant is not None
    assert not deactivated_merchant.is_active_merchant


@pytest.mark.integration
def test_anonymous_client_is_rejected_by_default(api):
    """DRF denies by default; a public endpoint has to opt in with AllowAny."""
    response = api.get("/api/orders/")
    assert response.status_code == 401


@pytest.mark.integration
def test_media_is_isolated_per_test(settings, tmp_path):
    """[T15-BE-MEDIA] Nothing lands in server/media/ during a test run."""
    assert settings.MEDIA_ROOT == tmp_path / "media"
    assert settings.MEDIA_ROOT.exists()
