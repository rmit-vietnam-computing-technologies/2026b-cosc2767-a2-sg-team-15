# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 09/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every case. Endpoint shapes and the
#   storefront visibility rules are taken from apps/catalog/views.py and
#   apps/catalog/models.py. References:
#   Django REST Framework testing, https://www.django-rest-framework.org/api-guide/testing/
#   pytest-django database access, https://pytest-django.readthedocs.io/en/latest/database.html

"""
Integration tests: the storefront API against the database.

The first test is the brief's "the shop endpoint actually returns products":
it fails when the database is unreachable, unmigrated or empty. The rest
cover storefront visibility rules enforced in querysets.
"""

from decimal import Decimal

import pytest

from apps.reviews.models import Review, ReviewStatus

pytestmark = pytest.mark.integration


# ===========================================================================
# The API-to-database connection
# ===========================================================================


def test_shop_endpoint_returns_products_from_the_database(api, make_product):
    """Frontend to backend to database, in one assertion.

    Rows are written through the ORM and read back through HTTP. Nothing is
    stubbed, so a pass means the connection, the schema and the serializer
    all work together.
    """
    make_product(name="Hoodie")
    make_product(name="Tote bag")
    make_product(name="Enamel mug")

    response = api.get("/api/products/")

    assert response.status_code == 200
    assert response.data["count"] == 3
    names = {row["name"] for row in response.data["results"]}
    assert names == {"Hoodie", "Tote bag", "Enamel mug"}


def test_shop_response_carries_the_pagination_envelope(api, make_product):
    """The SPA's toolbar reads these four keys by name.

    Renaming one is a silent frontend break: the grid still renders, the
    pager quietly stops working. Cheap to assert, expensive to discover in
    the browser.
    """
    for _ in range(15):
        make_product()

    response = api.get("/api/products/")

    assert response.status_code == 200
    assert response.data["count"] == 15
    assert response.data["total_pages"] == 2
    assert response.data["current_page"] == 1
    assert response.data["page_size"] == 12
    assert len(response.data["results"]) == 12


def test_product_detail_is_addressed_by_slug(api, product):
    """Slugs, not primary keys — the URL the SPA builds its links from."""
    response = api.get(f"/api/products/{product.slug}/")

    assert response.status_code == 200
    assert response.data["sku"] == product.sku
    assert Decimal(response.data["price"]) == product.price


# ===========================================================================
# Storefront visibility
# ===========================================================================


def test_inactive_product_is_hidden_from_the_shop(api, make_product):
    make_product(name="On sale")
    make_product(name="Withdrawn", is_active=False)

    response = api.get("/api/products/")

    assert response.data["count"] == 1
    assert response.data["results"][0]["name"] == "On sale"


def test_inactive_product_detail_returns_404(api, make_product):
    """404 rather than a 200 with an "unavailable" flag.

    The storefront queryset is the only gate, so a withdrawn product is not
    addressable at all — there is no second code path that could leak it.
    """
    withdrawn = make_product(is_active=False)

    assert api.get(f"/api/products/{withdrawn.slug}/").status_code == 404


def test_inactive_brand_hides_its_products(api, brand, make_product):
    """Deactivating a seller's brand takes their catalogue with it.

    This is the rule that makes admin deactivation of a merchant actually
    mean something. The product rows are untouched and still active in their
    own right; it is the brand join that removes them.
    """
    make_product(name="Branded item", brand=brand)

    assert api.get("/api/products/").data["count"] == 1

    brand.is_active = False
    brand.save(update_fields=["is_active"])

    assert api.get("/api/products/").data["count"] == 0


def test_product_without_a_brand_stays_visible(api, make_product):
    """The nullable side of the brand join must not filter the row out.

    ``storefront()`` reads ``brand__isnull=True OR brand__is_active=True``.
    Written as a plain ``brand__is_active=True`` it would silently drop every
    unbranded product, and the shop would look fine right up until somebody
    added one.
    """
    make_product(name="Unbranded", brand=None)

    response = api.get("/api/products/")

    assert response.data["count"] == 1
    assert response.data["results"][0]["brand_name"] is None


# ===========================================================================
# Filtering, search and ordering
# ===========================================================================


def test_category_filter_narrows_the_grid(api, make_product, category, db):
    from apps.catalog.models import Category

    other = Category.objects.create(name="Stationery")
    make_product(name="In category", categories=[category])
    make_product(name="Elsewhere", categories=[other])

    response = api.get("/api/products/", {"category": category.slug})

    assert response.data["count"] == 1
    assert response.data["results"][0]["name"] == "In category"


def test_search_matches_the_name_case_insensitively(api, make_product):
    make_product(name="RMIT Hoodie")
    make_product(name="Enamel mug")

    response = api.get("/api/products/", {"search": "hoodie"})

    assert response.data["count"] == 1
    assert response.data["results"][0]["name"] == "RMIT Hoodie"


def test_price_ordering_is_applied(api, make_product):
    make_product(name="Dear", price=Decimal("80.00"))
    make_product(name="Cheap", price=Decimal("10.00"))
    make_product(name="Middling", price=Decimal("45.00"))

    response = api.get("/api/products/", {"ordering": "price_asc"})

    assert [row["name"] for row in response.data["results"]] == [
        "Cheap",
        "Middling",
        "Dear",
    ]


def test_unknown_ordering_key_falls_back_instead_of_failing(api, make_product):
    """The sort key is a whitelist lookup, not a field name passed through.

    An unrecognised value has to produce the default ordering. If it reached
    ``order_by()`` the request would 500 on a bad field name — and worse, a
    value that *is* a real field name would let a caller sort by anything in
    the table.
    """
    make_product()

    response = api.get("/api/products/", {"ordering": "'; DROP TABLE products"})

    assert response.status_code == 200
    assert response.data["count"] == 1


def test_search_suggestions_are_empty_without_a_term(api, make_product):
    make_product(name="RMIT Hoodie")

    assert api.get("/api/products/search/").data == []
    assert len(api.get("/api/products/search/", {"q": "hood"}).data) == 1


# ===========================================================================
# Ratings, computed at query time
# ===========================================================================


def test_rating_average_counts_only_approved_reviews(api, product, member):
    """Rejected reviews must not move the stars on the shop card.

    Ratings are annotated onto the queryset rather than stored on the
    product, so this is a live aggregate — the value the shop grid shows and
    the value the product page shows come from the same expression.
    """
    Review.objects.create(
        product=product,
        user=member,
        title="Great",
        rating=5,
        review="Excellent",
        status=ReviewStatus.APPROVED,
    )
    Review.objects.create(
        product=product,
        user=member,
        title="Spam",
        rating=1,
        review="Buy followers",
        status=ReviewStatus.REJECTED,
    )

    row = api.get("/api/products/").data["results"][0]

    assert row["rating_avg"] == 5.0
    assert row["rating_count"] == 1


def test_products_with_no_reviews_report_zero_not_null(api, product):
    """``Coalesce`` to 0.0 — the SPA renders the number straight into a width."""
    row = api.get("/api/products/").data["results"][0]

    assert row["rating_avg"] == 0
    assert row["rating_count"] == 0


# ===========================================================================
# Categories and brands
# ===========================================================================


def test_category_and_brand_lists_expose_active_rows_with_counts(
    api, brand, category, make_product
):
    make_product(brand=brand, categories=[category])

    categories = api.get("/api/categories/").data
    brands = api.get("/api/brands/").data

    assert [row["slug"] for row in categories] == [category.slug]
    assert categories[0]["product_count"] == 1
    assert [row["slug"] for row in brands] == [brand.slug]
    assert brands[0]["product_count"] == 1
