# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every case. The rule that only approved
#   reviews count towards a rating is documented in
#   ProductQuerySet.with_ratings in apps/catalog/models.py. Reference:
#   Django aggregation, https://docs.djangoproject.com/en/5.1/topics/db/aggregation/

"""
Integration tests: reviews and moderation.

Ratings are computed at query time from approved reviews rather than stored
on the product, which means moderating a review has to change the stars
everywhere at once with nothing to keep in step. These tests assert that it
does — from the shop grid, the product detail and the review summary, all
three of which read the same aggregate.

The failure mode being guarded against is specific and was real in the
application this replaces: it averaged over every review regardless of
status while only *displaying* the approved ones, so the stars on a shop card
disagreed with the reviews visible on the product page.
"""

import pytest

from apps.reviews.models import Review, ReviewStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def reviewed_product(product, member, other_member):
    """One product with two approved reviews, five stars and one star.

    Returns ``(product, five_star_review, one_star_review)``. The average
    starts at 3.0, so rejecting either review moves it somewhere unambiguous
    and a test cannot pass by accident.
    """
    five = Review.objects.create(
        product=product,
        user=member,
        title="Excellent",
        rating=5,
        review="Exactly as described.",
        status=ReviewStatus.APPROVED,
    )
    one = Review.objects.create(
        product=product,
        user=other_member,
        title="Terrible",
        rating=1,
        review="Not as described.",
        status=ReviewStatus.APPROVED,
    )
    return product, five, one


def _shop_card(api, product):
    """The product as the shop grid sees it."""
    rows = api.get("/api/products/").data["results"]
    return next(row for row in rows if row["id"] == product.pk)


# ===========================================================================
# Writing a review
# ===========================================================================


def test_a_member_can_review_a_product(as_user, member, product):
    response = as_user(member).post(
        "/api/reviews/",
        {
            "product": product.pk,
            "title": "Good buy",
            "rating": 4,
            "review": "Happy with it.",
        },
        format="json",
    )

    assert response.status_code == 201
    review = Review.objects.get(pk=response.data["id"])
    assert review.user == member
    # Visible straight away, matching the behaviour of the app this replaces.
    assert review.status == ReviewStatus.APPROVED


def test_a_new_review_moves_the_product_average_immediately(
    api, as_user, member, product
):
    assert _shop_card(api, product)["rating_avg"] == 0

    as_user(member).post(
        "/api/reviews/",
        {"product": product.pk, "title": "Good", "rating": 4, "review": "Nice."},
        format="json",
    )

    card = _shop_card(api, product)
    assert card["rating_avg"] == 4.0
    assert card["rating_count"] == 1


def test_the_review_author_is_taken_from_the_token_not_the_body(
    as_user, member, other_member, product
):
    """A review cannot be posted in somebody else's name.

    ``perform_create`` sets the user from the request, so a ``user`` key in
    the body is ignored rather than trusted.
    """
    response = as_user(member).post(
        "/api/reviews/",
        {
            "product": product.pk,
            "title": "Planted",
            "rating": 5,
            "review": "Suspiciously positive.",
            "user": other_member.pk,
        },
        format="json",
    )

    assert response.status_code == 201
    assert Review.objects.get(pk=response.data["id"]).user == member


@pytest.mark.parametrize("rating", [0, 6, -1])
def test_a_rating_outside_one_to_five_is_refused(as_user, member, product, rating):
    response = as_user(member).post(
        "/api/reviews/",
        {"product": product.pk, "title": "Out of range", "rating": rating,
         "review": "..."},
        format="json",
    )

    assert response.status_code == 400


# ===========================================================================
# Moderation
# ===========================================================================


def test_rejecting_a_review_recomputes_the_product_average(
    api, as_user, admin, reviewed_product
):
    """The moderation queue changes what the shop grid shows.

    Nothing is stored on the product, so there is no denormalised column to
    fall out of step — rejecting the one-star review moves the average from
    3.0 to 5.0 on the next read, everywhere.
    """
    product, _five, one = reviewed_product
    assert _shop_card(api, product)["rating_avg"] == 3.0

    response = as_user(admin).post(f"/api/manage/reviews/{one.pk}/reject/")

    assert response.status_code == 200
    card = _shop_card(api, product)
    assert card["rating_avg"] == 5.0
    assert card["rating_count"] == 1


def test_approving_a_review_puts_it_back_into_the_average(
    api, as_user, admin, reviewed_product
):
    """Moderation is reversible, and the aggregate follows it back."""
    product, _five, one = reviewed_product
    as_user(admin).post(f"/api/manage/reviews/{one.pk}/reject/")
    assert _shop_card(api, product)["rating_avg"] == 5.0

    as_user(admin).post(f"/api/manage/reviews/{one.pk}/approve/")

    assert _shop_card(api, product)["rating_avg"] == 3.0


def test_a_rejected_review_disappears_from_the_product_page(
    api, as_user, admin, reviewed_product
):
    """The list and the average have to agree — they read the same rule."""
    product, _five, one = reviewed_product

    as_user(admin).post(f"/api/manage/reviews/{one.pk}/reject/")

    response = api.get(f"/api/products/{product.slug}/reviews/")
    assert response.status_code == 200
    assert [row["title"] for row in response.data["results"]] == ["Excellent"]
    assert response.data["summary"]["average"] == 5.0
    assert response.data["summary"]["total_reviews"] == 1


def test_the_summary_breakdown_matches_the_visible_reviews(api, reviewed_product):
    """The per-star bars, computed server-side.

    The original built this in the browser from a single page of reviews, so
    the summary disagreed with the stars as soon as there were more reviews
    than fitted on one page.
    """
    product, _five, _one = reviewed_product

    summary = api.get(f"/api/products/{product.slug}/reviews/").data["summary"]

    assert summary["average"] == 3.0
    assert summary["total_reviews"] == 2
    assert summary["breakdown"] == {"1": 1, "2": 0, "3": 0, "4": 0, "5": 1}


def test_the_moderation_queue_can_be_filtered_by_status(
    as_user, admin, reviewed_product
):
    product, _five, one = reviewed_product
    as_user(admin).post(f"/api/manage/reviews/{one.pk}/reject/")

    approved = as_user(admin).get("/api/manage/reviews/", {"status": "approved"})
    rejected = as_user(admin).get("/api/manage/reviews/", {"status": "rejected"})

    assert approved.data["count"] == 1
    assert rejected.data["count"] == 1
    assert rejected.data["results"][0]["id"] == one.pk


def test_a_member_cannot_moderate(as_user, member, reviewed_product):
    _product, _five, one = reviewed_product

    assert as_user(member).post(
        f"/api/manage/reviews/{one.pk}/reject/"
    ).status_code == 403


def test_deleting_a_review_removes_it_from_the_average(
    api, as_user, member, reviewed_product
):
    """The author's own delete, and the aggregate follows."""
    product, five, _one = reviewed_product

    assert as_user(member).delete(f"/api/reviews/{five.pk}/").status_code == 204

    assert _shop_card(api, product)["rating_avg"] == 1.0
    assert _shop_card(api, product)["rating_count"] == 1


# ===========================================================================
# Wishlist
# ===========================================================================


def test_wishlist_toggle_is_idempotent(as_user, member, product):
    """Two likes for one product must not become two rows.

    The unique constraint on (user, product) plus ``update_or_create`` is
    what makes this safe. The original emulated an upsert by hand and could
    race into duplicate rows, which then broke the "is this liked?" lookup on
    the shop page.
    """
    client = as_user(member)
    body = {"product": product.pk, "is_liked": True}

    assert client.post("/api/wishlist/", body, format="json").status_code == 200
    assert client.post("/api/wishlist/", body, format="json").status_code == 200

    assert len(client.get("/api/wishlist/").data) == 1


def test_unliking_removes_the_product_from_the_wishlist(as_user, member, product):
    client = as_user(member)

    client.post("/api/wishlist/", {"product": product.pk, "is_liked": True},
                format="json")
    client.post("/api/wishlist/", {"product": product.pk, "is_liked": False},
                format="json")

    assert client.get("/api/wishlist/").data == []


def test_the_shop_grid_reports_whether_the_caller_liked_a_product(
    api, as_user, member, product
):
    """Anonymous callers get ``is_liked: false`` rather than an error.

    The flag is annotated from a verified token, so there is no way to have
    the wishlist join run against a user id from a forged one.
    """
    assert _shop_card(api, product)["is_liked"] is False

    as_user(member).post(
        "/api/wishlist/", {"product": product.pk, "is_liked": True}, format="json"
    )

    rows = as_user(member).get("/api/products/").data["results"]
    assert rows[0]["is_liked"] is True
