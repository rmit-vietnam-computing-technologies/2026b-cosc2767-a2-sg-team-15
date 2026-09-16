# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   verified every fixture. Reference: pytest-django helpers,
#   https://pytest-django.readthedocs.io/en/latest/helpers.html

"""Shared fixtures for the integration suite."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.catalog.models import Brand, Category, Product


@pytest.fixture(autouse=True)
def _isolated_media(settings, tmp_path):
    # Uploads go to a per-test directory, never to server/media/ on the laptop.
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    return settings.MEDIA_ROOT


@pytest.fixture
def as_user():
    # force_authenticate skips the JWT round trip; these tests are about orders, not tokens.
    def _as_user(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _as_user


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
def category(db):
    return Category.objects.create(name="Test Category")


@pytest.fixture
def brand(db):
    return Brand.objects.create(name="Test Brand")


@pytest.fixture
def make_product(db, brand, category):
    # Factory: make_product(quantity=1, taxable=True). Stock and tax vary per test.
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
    return make_product()


@pytest.fixture
def approved_card():
    return "4242424242424242"


@pytest.fixture
def declined_card():
    return "4000000000000002"


@pytest.fixture
def card_payload(approved_card):
    # Expiry far out so the suite never rots on a date nobody chose.
    def _card_payload(number=None, **overrides):
        payload = {
            "number": number or approved_card,
            "exp_month": 12,
            "exp_year": 2099,
            "cvc": "123",
            "name_on_card": "Test Shopper",
        }
        payload.update(overrides)
        return payload

    return _card_payload


@pytest.fixture
def checkout(as_user, card_payload):
    # Posts through the real endpoint so serializer, permission, service and transaction all run.
    def _checkout(user, lines, number=None, **extra):
        body = {
            "items": [{"product": p.pk, "quantity": q} for p, q in lines],
            "payment": card_payload(number),
        }
        body.update(extra)
        return as_user(user).post("/api/orders/", body, format="json")

    return _checkout
