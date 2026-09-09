# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 09/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every case. The ordering guarantee under
#   test (stock checked, card authorised, then rows written) is documented in
#   the docstring of apps/orders/services.create_order. References:
#   Django transactions, https://docs.djangoproject.com/en/5.1/topics/db/transactions/
#   DRF status codes, https://www.django-rest-framework.org/api-guide/status-codes/

"""
Integration tests: checkout, through ``POST /api/orders/``.

The key test is ``test_declined_card_leaves_no_order_and_takes_no_stock``:
the obvious implementation (take stock, refund on decline) lets a stream of
failed checkouts empty a shelf.
"""

from decimal import Decimal

import pytest
from django.core import mail

from apps.orders.models import Order, OrderItemStatus, OrderStatus, PaymentStatus

pytestmark = pytest.mark.integration


# ===========================================================================
# The happy path
# ===========================================================================


def test_checkout_creates_an_order_and_decrements_stock_once(
    member, product, checkout
):
    """Stock moves by exactly the quantity bought. Not twice, not none."""
    response = checkout(member, [(product, 3)])

    assert response.status_code == 201
    product.refresh_from_db()
    assert product.quantity == 7

    order = Order.objects.get(pk=response.data["id"])
    assert order.user == member
    assert order.status == OrderStatus.PLACED
    assert order.payment_status == PaymentStatus.PAID
    assert order.items.count() == 1
    assert order.items.first().quantity == 3


def test_totals_are_computed_from_the_database_not_the_request(
    member, make_product, checkout
):
    """A shopper cannot set their own price.

    The extra keys below are what an attacker would add to the request body.
    ``OrderCreateSerializer`` declares only ``items`` and ``payment``, so they
    are dropped on the way in and the total is re-derived from the product
    rows. The application this replaces stored the total the client sent.
    """
    product = make_product(price=Decimal("50.00"))

    response = checkout(
        member,
        [(product, 2)],
        # None of this should survive.
        total="0.01",
        subtotal="0.01",
        price="0.01",
    )

    assert response.status_code == 201
    assert Decimal(response.data["subtotal"]) == Decimal("100.00")
    assert Decimal(response.data["total"]) == Decimal("100.00")


def test_tax_is_applied_only_to_taxable_products(member, make_product, checkout):
    """Tax is a server-side decision, read from the product's own flag."""
    taxed = make_product(price=Decimal("100.00"), taxable=True)
    untaxed = make_product(price=Decimal("100.00"), taxable=False)

    response = checkout(member, [(taxed, 1), (untaxed, 1)])

    assert response.status_code == 201
    assert Decimal(response.data["subtotal"]) == Decimal("200.00")
    # 5% of the taxable line only.
    assert Decimal(response.data["total_tax"]) == Decimal("5.00")
    assert Decimal(response.data["total"]) == Decimal("205.00")


def test_duplicate_lines_for_one_product_are_collapsed(
    member, product, as_user, card_payload
):
    """Two lines for the same product must take stock once, for the sum.

    Without the collapse, the second line overwrites the first in the lock
    dictionary and the shopper is charged for one but shipped two — or the
    stock check passes on each line separately and oversells the row.
    """
    response = as_user(member).post(
        "/api/orders/",
        {
            "items": [
                {"product": product.pk, "quantity": 2},
                {"product": product.pk, "quantity": 3},
            ],
            "payment": card_payload(),
        },
        format="json",
    )

    assert response.status_code == 201
    product.refresh_from_db()
    assert product.quantity == 5

    order = Order.objects.get(pk=response.data["id"])
    assert order.items.count() == 1
    assert order.items.first().quantity == 5


def test_line_items_snapshot_the_product(member, brand, make_product, checkout):
    """The order must still read correctly after the product changes.

    Name, slug and brand are copied onto the line at purchase time. Following
    a live foreign key instead is what let the original corrupt historical
    orders every time somebody renamed a product.
    """
    product = make_product(name="Original name", price=Decimal("25.00"), brand=brand)

    response = checkout(member, [(product, 1)])
    assert response.status_code == 201

    product.name = "Renamed later"
    product.price = Decimal("999.00")
    product.save(update_fields=["name", "price"])

    item = Order.objects.get(pk=response.data["id"]).items.first()
    assert item.product_name == "Original name"
    assert item.brand_name == brand.name
    assert item.purchase_price == Decimal("25.00")


def test_order_confirmation_email_is_sent(member, product, checkout):
    """The customer-facing notification, captured by the locmem backend."""
    response = checkout(member, [(product, 1)])

    assert response.status_code == 201
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [member.email]
    assert str(response.data["id"]) in mail.outbox[0].subject


# ===========================================================================
# The decline path
# ===========================================================================


def test_declined_card_leaves_no_order_and_takes_no_stock(
    member, product, checkout, declined_card
):
    """The single most valuable assertion in the suite.

    Three things have to hold together: the response is a 402, no Order row
    exists, and the stock is untouched. Asserting only the status code would
    pass against an implementation that decremented the stock and then failed
    to put it back — which is precisely the bug worth catching, because the
    shelf empties silently while every response still looks correct.
    """
    starting_stock = product.quantity

    response = checkout(member, [(product, 2)], number=declined_card)

    assert response.status_code == 402
    assert Order.objects.count() == 0

    product.refresh_from_db()
    assert product.quantity == starting_stock


def test_decline_carries_a_machine_readable_code(member, product, checkout):
    """The SPA highlights a field from ``decline_code``, not from the sentence."""
    response = checkout(member, [(product, 1)], number="4000000000009995")

    assert response.status_code == 402
    assert response.data["decline_code"] == "insufficient_funds"
    assert response.data["detail"]


def test_repeated_declines_never_erode_stock(member, product, checkout, declined_card):
    """The property that makes decline numbers safe to fire from CI.

    A post-deploy smoke check that runs on every deployment must not cost
    inventory. Five declines in a row leave the shelf exactly as it was.
    """
    starting_stock = product.quantity

    for _ in range(5):
        assert checkout(member, [(product, 1)], number=declined_card).status_code == 402

    product.refresh_from_db()
    assert product.quantity == starting_stock
    assert Order.objects.count() == 0


def test_declined_checkout_sends_no_confirmation_email(
    member, product, checkout, declined_card
):
    """No order means no receipt. The exception unwinds before the mail call."""
    checkout(member, [(product, 1)], number=declined_card)

    assert mail.outbox == []


# ===========================================================================
# Rejected baskets
# ===========================================================================


def test_quantity_beyond_stock_is_refused(member, make_product, checkout):
    product = make_product(quantity=2)

    response = checkout(member, [(product, 3)])

    assert response.status_code == 400
    assert Order.objects.count() == 0
    product.refresh_from_db()
    assert product.quantity == 2


def test_inactive_product_cannot_be_bought(member, make_product, checkout):
    """Withdrawn from the shop is withdrawn from checkout too.

    The product is still addressable by primary key, so the serializer lets
    the id through — the refusal has to come from the service layer. A check
    that lived only in the storefront queryset would leave this open.
    """
    product = make_product(is_active=False)

    response = checkout(member, [(product, 1)])

    assert response.status_code == 400
    assert Order.objects.count() == 0


def test_empty_basket_is_refused(member, as_user, card_payload):
    response = as_user(member).post(
        "/api/orders/", {"items": [], "payment": card_payload()}, format="json"
    )

    assert response.status_code == 400


def test_unknown_product_id_is_refused(member, as_user, card_payload):
    response = as_user(member).post(
        "/api/orders/",
        {"items": [{"product": 999999, "quantity": 1}], "payment": card_payload()},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"number": "4242424242424241"}, "number"),
        ({"cvc": "12"}, "cvc"),
        ({"exp_month": 1, "exp_year": 2020}, "exp_year"),
    ],
    ids=["fails-luhn", "wrong-cvc-length", "expired"],
)
def test_card_validation_rejects_before_reaching_the_gateway(
    member, product, as_user, card_payload, overrides, field
):
    """400, not 402.

    A malformed card is the shopper's typo; a declined card is the bank's
    decision. Collapsing the two would leave the checkout form unable to tell
    "fix this field" apart from "try a different card".
    """
    response = as_user(member).post(
        "/api/orders/",
        {
            "items": [{"product": product.pk, "quantity": 1}],
            "payment": card_payload(**overrides),
        },
        format="json",
    )

    assert response.status_code == 400
    assert field in response.data["payment"]
    assert Order.objects.count() == 0


# ===========================================================================
# What the response is allowed to contain
# ===========================================================================


def test_card_number_is_never_echoed_back(member, product, checkout, approved_card):
    """Only the brand and last four digits survive the request.

    Every field on PaymentSerializer is write_only. Asserting on the rendered
    body rather than the model is deliberate: a field added to the serializer
    later would leak here first.
    """
    response = checkout(member, [(product, 1)])
    body = str(response.data)

    assert approved_card not in body
    assert "123" not in response.data.get("card_last4", "")
    assert response.data["card_brand"] == "visa"
    assert response.data["card_last4"] == approved_card[-4:]
    assert response.data["payment_reference"]


def test_new_line_items_start_unprocessed(member, product, checkout):
    order = Order.objects.get(pk=checkout(member, [(product, 1)]).data["id"])

    assert order.items.first().status == OrderItemStatus.NOT_PROCESSED


# ===========================================================================
# Access
# ===========================================================================


def test_anonymous_checkout_is_rejected(api, product, card_payload):
    response = api.post(
        "/api/orders/",
        {
            "items": [{"product": product.pk, "quantity": 1}],
            "payment": card_payload(),
        },
        format="json",
    )

    assert response.status_code == 401
    assert Order.objects.count() == 0
