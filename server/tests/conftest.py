# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every fixture. Reference:
#   pytest-django fixtures, https://pytest-django.readthedocs.io/en/latest/helpers.html

"""
Shared fixtures for the whole suite.

Four roles matter to this application — anonymous, member, merchant and admin —
because almost every permission decision in the API reads ``User.role``. They
are defined once here so the authorisation matrix in Step 4 can parametrise
over them rather than rebuilding users in every module.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.catalog.models import Brand, Category, Product
from apps.merchants.models import Merchant, MerchantStatus

# --------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_media(settings, tmp_path):
    """[T15-BE-MEDIA] Every test writes uploads to its own directory.

    Autouse, because a single test that forgets it pollutes ``server/media/``
    on a developer's laptop and leaves the working tree dirty. tmp_path is
    per-test, so two tests uploading the same filename cannot collide either.
    """
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    return settings.MEDIA_ROOT


# --------------------------------------------------------------------------
# Clients
# --------------------------------------------------------------------------


@pytest.fixture
def api():
    """An unauthenticated API client — the anonymous visitor."""
    return APIClient()


@pytest.fixture
def as_user():
    """Factory: ``as_user(some_user)`` returns a client acting as that user.

    Uses ``force_authenticate`` rather than logging in over ``/api/auth/login/``.
    That skips the JWT round trip, which is the point: a permissions test
    should fail because of permissions, not because a token expired or the
    login endpoint changed shape. The real token flow is exercised on its own
    in the authentication tests, where it is the subject rather than setup.
    """

    def _as_user(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _as_user


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------


@pytest.fixture
def member(db):
    return User.objects.create_user(
        email="member@test.local",
        password="MemberPass123!",
        first_name="Mia",
        last_name="Member",
        role=Role.MEMBER,
    )


@pytest.fixture
def other_member(db):
    """A second member, for proving one user cannot read another's data."""
    return User.objects.create_user(
        email="other@test.local",
        password="OtherPass123!",
        role=Role.MEMBER,
    )


@pytest.fixture
def admin(db):
    return User.objects.create_superuser(
        email="admin@test.local",
        password="AdminPass123!",
        first_name="Ada",
        last_name="Admin",
    )


@pytest.fixture
def merchant_brand(db):
    return Brand.objects.create(name="Test Merchant Brand")


@pytest.fixture
def merchant(db, merchant_brand):
    """An approved, active seller.

    Three separate things have to line up before ``user.is_active_merchant``
    is true: the role, an existing Merchant record, and that record being
    active. Building it correctly once here stops every merchant test from
    re-deriving it and getting one part subtly wrong.
    """
    record = Merchant.objects.create(
        name="Test Merchant",
        email="merchant@test.local",
        brand_name="Test Merchant Brand",
        status=MerchantStatus.APPROVED,
        is_active=True,
        brand=merchant_brand,
    )
    user = User.objects.create_user(
        email="merchant@test.local",
        password="MerchantPass123!",
        role=Role.MERCHANT,
    )
    user.merchant = record
    user.save(update_fields=["merchant"])
    return user


@pytest.fixture
def deactivated_merchant(db):
    """[REQ-5] A seller whose approval was withdrawn.

    Role is still MERCHANT and the Merchant record still exists, so anything
    that checks only the role lets this account through. It must not be able
    to touch products. This is the case a naive permission check misses.
    """
    record = Merchant.objects.create(
        name="Former Merchant",
        email="former@test.local",
        status=MerchantStatus.APPROVED,
        is_active=False,
    )
    user = User.objects.create_user(
        email="former@test.local",
        password="FormerPass123!",
        role=Role.MERCHANT,
    )
    user.merchant = record
    user.save(update_fields=["merchant"])
    return user


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------


@pytest.fixture
def category(db):
    return Category.objects.create(name="Test Category")


@pytest.fixture
def brand(db):
    return Brand.objects.create(name="Test Brand")


@pytest.fixture
def make_product(db, brand, category):
    """Factory with sensible defaults; override any field per test.

        product = make_product(quantity=1, taxable=True)

    A factory rather than a fixed fixture because stock level and taxability
    are the two things checkout tests need to vary, and a shared immutable
    product would force each of them to mutate it.
    """
    counter = {"n": 0}

    def _make_product(**overrides):
        counter["n"] += 1
        n = counter["n"]
        fields = {
            "sku": f"TEST-SKU-{n:03d}",
            "name": f"Test Product {n}",
            "price": Decimal("99.95"),
            "quantity": 10,
            "taxable": False,
            "is_active": True,
            "brand": brand,
        }
        fields.update(overrides)
        categories = fields.pop("categories", [category])
        product = Product.objects.create(**fields)
        if categories:
            product.categories.set(categories)
        return product

    return _make_product


@pytest.fixture
def product(make_product):
    """One in-stock, non-taxable product. The common case."""
    return make_product()


# --------------------------------------------------------------------------
# Payment cards
# --------------------------------------------------------------------------


@pytest.fixture
def approved_card():
    """[REQ-5] Simulated gateway, so no provider, account or network call.

    That is what makes these numbers safe to fire repeatedly from CI and from
    post-deploy checks on a private subnet.
    """
    return "4242424242424242"


@pytest.fixture
def declined_card():
    """A generic decline. Leaves no order behind and takes no stock."""
    return "4000000000000002"
