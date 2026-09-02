# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every expected status code against
#   apps/core/permissions.py and each viewset's permission_classes.
#   References:
#   DRF permissions, https://www.django-rest-framework.org/api-guide/permissions/
#   pytest parametrize, https://docs.pytest.org/en/stable/how-to/parametrize.html

"""
[T15-BE-TEST][REQ-5] The authorisation matrix.

Every endpoint, against every role, asserting the exact status code. This is
the suite that justifies choosing pytest over ``manage.py test``: written as
parameters it is one function and roughly a hundred individually named
results in the Jenkins JUnit view, so a regression names the endpoint and the
role that broke. The same coverage under ``unittest`` is a hundred hand-written
methods, or one loop that reports a single pass or fail and tells you nothing.

Reading the table below is the fastest way to understand who may do what.

Three status codes, three different meanings, and the distinction matters:

    401  no credentials were presented
    403  credentials were presented and are not enough
    404  the row exists, but not inside the queryset this caller can see

That last one is deliberate. Scoping the queryset rather than checking
ownership per handler means another seller's product id is indistinguishable
from one that never existed, so the endpoint cannot be used to probe for
which ids are real.
"""

import pytest

from apps.catalog.models import Product

pytestmark = pytest.mark.integration

ANONYMOUS = "anonymous"
MEMBER = "member"
MERCHANT = "merchant"
ADMIN = "admin"

ROLES = [ANONYMOUS, MEMBER, MERCHANT, ADMIN]


# ---------------------------------------------------------------------------
# The matrix
#
# (method, path, {role: expected status})
#
# 400 appears where a role is *allowed* through and then fails validation on
# an empty body. That is the correct expectation: it proves the request
# reached the serializer rather than being stopped by a permission class, and
# a test that accepted "anything but 403" would pass against a broken deny.
# ---------------------------------------------------------------------------

MATRIX = [
    # --- probes and public configuration -----------------------------------
    ("get", "/healthz/", {ANONYMOUS: 200, MEMBER: 200, MERCHANT: 200, ADMIN: 200}),
    ("get", "/readyz/", {ANONYMOUS: 200, MEMBER: 200, MERCHANT: 200, ADMIN: 200}),
    ("get", "/api/version/", {ANONYMOUS: 200, MEMBER: 200, MERCHANT: 200, ADMIN: 200}),
    ("get", "/api/config/", {ANONYMOUS: 200, MEMBER: 200, MERCHANT: 200, ADMIN: 200}),
    # --- public storefront -------------------------------------------------
    ("get", "/api/products/", {ANONYMOUS: 200, MEMBER: 200, MERCHANT: 200, ADMIN: 200}),
    (
        "get",
        "/api/products/search/",
        {ANONYMOUS: 200, MEMBER: 200, MERCHANT: 200, ADMIN: 200},
    ),
    (
        "get",
        "/api/categories/",
        {ANONYMOUS: 200, MEMBER: 200, MERCHANT: 200, ADMIN: 200},
    ),
    ("get", "/api/brands/", {ANONYMOUS: 200, MEMBER: 200, MERCHANT: 200, ADMIN: 200}),
    # --- the customer's own records ----------------------------------------
    ("get", "/api/orders/", {ANONYMOUS: 401, MEMBER: 200, MERCHANT: 200, ADMIN: 200}),
    ("post", "/api/orders/", {ANONYMOUS: 401, MEMBER: 400, MERCHANT: 400, ADMIN: 400}),
    (
        "get",
        "/api/addresses/",
        {ANONYMOUS: 401, MEMBER: 200, MERCHANT: 200, ADMIN: 200},
    ),
    ("get", "/api/wishlist/", {ANONYMOUS: 401, MEMBER: 200, MERCHANT: 200, ADMIN: 200}),
    ("get", "/api/users/me/", {ANONYMOUS: 401, MEMBER: 200, MERCHANT: 200, ADMIN: 200}),
    ("post", "/api/reviews/", {ANONYMOUS: 401, MEMBER: 400, MERCHANT: 400, ADMIN: 400}),
    # --- administration ----------------------------------------------------
    # Listing every account was authenticated but unrestricted in the
    # application this replaces, so any signed-in member could page through
    # the whole user table.
    ("get", "/api/users/", {ANONYMOUS: 401, MEMBER: 403, MERCHANT: 403, ADMIN: 200}),
    (
        "get",
        "/api/manage/merchants/",
        {ANONYMOUS: 401, MEMBER: 403, MERCHANT: 403, ADMIN: 200},
    ),
    (
        "get",
        "/api/manage/categories/",
        {ANONYMOUS: 401, MEMBER: 403, MERCHANT: 403, ADMIN: 200},
    ),
    (
        "get",
        "/api/manage/reviews/",
        {ANONYMOUS: 401, MEMBER: 403, MERCHANT: 403, ADMIN: 200},
    ),
    # --- seller surface ----------------------------------------------------
    # A merchant reaches these; a member does not.
    (
        "get",
        "/api/manage/products/",
        {ANONYMOUS: 401, MEMBER: 403, MERCHANT: 200, ADMIN: 200},
    ),
    (
        "post",
        "/api/manage/products/",
        {ANONYMOUS: 401, MEMBER: 403, MERCHANT: 400, ADMIN: 400},
    ),
    (
        "get",
        "/api/manage/brands/",
        {ANONYMOUS: 401, MEMBER: 403, MERCHANT: 200, ADMIN: 200},
    ),
    # Creating a brand is an admin action even for a seller: a brand is made
    # for them when their application is approved.
    (
        "post",
        "/api/manage/brands/",
        {ANONYMOUS: 401, MEMBER: 403, MERCHANT: 403, ADMIN: 400},
    ),
]


def _client_for(role, api, as_user, member, merchant, admin):
    return {
        ANONYMOUS: api,
        MEMBER: as_user(member),
        MERCHANT: as_user(merchant),
        ADMIN: as_user(admin),
    }[role]


# Named rows, so a failure in Jenkins reads
# "test_authorisation_matrix[admin-GET /api/manage/brands/]" rather than
# "[admin-expected21]". The whole argument for parametrising this suite is
# that the report names the endpoint and the role; unnamed parameters throw
# that away and leave an index to count through by hand.
MATRIX_PARAMS = [
    pytest.param(method, path, expected, id=f"{method.upper()} {path}")
    for method, path, expected in MATRIX
]


@pytest.mark.parametrize(("method", "path", "expected"), MATRIX_PARAMS)
@pytest.mark.parametrize("role", ROLES)
def test_authorisation_matrix(
    method, path, expected, role, api, as_user, member, merchant, admin
):
    """[REQ-5] One row of the matrix: this role, this endpoint, this code."""
    client = _client_for(role, api, as_user, member, merchant, admin)

    response = getattr(client, method)(path, {}, format="json")

    assert response.status_code == expected[role], (
        f"{method.upper()} {path} as {role}: "
        f"expected {expected[role]}, got {response.status_code}"
    )


# ===========================================================================
# Queryset scoping — 404 rather than 403
# ===========================================================================


def test_merchant_sees_only_their_own_products(
    as_user, merchant, rival_merchant, make_product, merchant_brand
):
    """The list is scoped, not filtered client-side."""
    make_product(name="Mine", brand=merchant_brand)
    make_product(name="Theirs", brand=rival_merchant.merchant.brand)

    response = as_user(merchant).get("/api/manage/products/")

    assert response.status_code == 200
    assert [row["name"] for row in response.data["results"]] == ["Mine"]


def test_another_sellers_product_is_404_not_403(
    as_user, merchant, rival_merchant, make_product
):
    """[REQ-5] The endpoint must not confirm that the id exists.

    403 would answer a question the caller is not entitled to ask: it says
    "this row is real, you just cannot have it". Scoping the queryset makes
    somebody else's id and a nonexistent id indistinguishable.
    """
    theirs = make_product(name="Theirs", brand=rival_merchant.merchant.brand)

    response = as_user(merchant).get(f"/api/manage/products/{theirs.pk}/")

    assert response.status_code == 404
    # A genuinely nonexistent id answers identically.
    assert as_user(merchant).get("/api/manage/products/999999/").status_code == 404


def test_merchant_cannot_edit_another_sellers_product(
    as_user, merchant, rival_merchant, make_product
):
    theirs = make_product(name="Theirs", brand=rival_merchant.merchant.brand)

    response = as_user(merchant).patch(
        f"/api/manage/products/{theirs.pk}/", {"name": "Hijacked"}, format="json"
    )

    assert response.status_code == 404
    theirs.refresh_from_db()
    assert theirs.name == "Theirs"


def test_admin_sees_every_sellers_products(
    as_user, admin, merchant_brand, rival_merchant, make_product
):
    make_product(name="Mine", brand=merchant_brand)
    make_product(name="Theirs", brand=rival_merchant.merchant.brand)

    response = as_user(admin).get("/api/manage/products/")

    assert response.status_code == 200
    assert {row["name"] for row in response.data["results"]} == {"Mine", "Theirs"}


# ===========================================================================
# The deactivated seller
# ===========================================================================


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/manage/products/"),
        ("post", "/api/manage/products/"),
        ("get", "/api/manage/brands/"),
    ],
)
def test_deactivated_merchant_is_refused(as_user, deactivated_merchant, method, path):
    """[REQ-5] The case a role-only permission check waves straight through.

    The role is still MERCHANT and the Merchant record still exists — only
    ``is_active`` changed. ``IsMerchant`` checks all three, which is why an
    admin withdrawing an approval takes effect immediately rather than at the
    seller's next login.
    """
    response = getattr(as_user(deactivated_merchant), method)(path, {}, format="json")

    assert response.status_code == 403


# ===========================================================================
# Order scoping
# ===========================================================================


def test_member_cannot_read_another_members_order(
    as_user, member, other_member, product, checkout
):
    """The fix for an endpoint that was authenticated but not authorised.

    In the original, any signed-in member could page through the entire order
    history of the store.
    """
    order_id = checkout(member, [(product, 1)]).data["id"]

    assert as_user(other_member).get(f"/api/orders/{order_id}/").status_code == 404
    assert as_user(other_member).get("/api/orders/").data["count"] == 0


def test_admin_can_read_every_order(as_user, admin, member, product, checkout):
    order_id = checkout(member, [(product, 1)]).data["id"]

    response = as_user(admin).get(f"/api/orders/{order_id}/")

    assert response.status_code == 200
    assert response.data["customer_email"] == member.email


def test_member_sees_only_their_own_orders_in_the_list(
    as_user, member, other_member, make_product, checkout
):
    mine = make_product()
    theirs = make_product()
    checkout(member, [(mine, 1)])
    checkout(other_member, [(theirs, 1)])

    assert as_user(member).get("/api/orders/").data["count"] == 1
    assert as_user(other_member).get("/api/orders/").data["count"] == 1
    assert Product.objects.count() == 2


# ===========================================================================
# Reviews
# ===========================================================================


def test_member_cannot_edit_another_members_review(
    as_user, member, other_member, product
):
    """Editing and deleting a review were unauthenticated in the original."""
    created = as_user(member).post(
        "/api/reviews/",
        {
            "product": product.pk,
            "title": "Good",
            "rating": 5,
            "review": "Happy with it",
        },
        format="json",
    )
    assert created.status_code == 201
    review_id = created.data["id"]

    response = as_user(other_member).patch(
        f"/api/reviews/{review_id}/", {"title": "Hijacked"}, format="json"
    )

    assert response.status_code == 403
    assert as_user(other_member).delete(f"/api/reviews/{review_id}/").status_code == 403
