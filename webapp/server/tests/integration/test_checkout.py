# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   mutation-checked every case. The stock-then-authorise-then-write order is
#   documented in apps/orders/services.create_order. Reference: Django
#   transactions, https://docs.djangoproject.com/en/5.1/topics/db/transactions/

"""Checkout through POST /api/orders/, against real PostgreSQL.

Money and stock are the two things this store cannot get wrong: totals come
from the database, stock moves exactly once, and a decline leaves nothing
behind.
"""

from decimal import Decimal

import pytest
from django.core import mail
from django.forms.models import model_to_dict

from apps.orders.models import Order, PaymentStatus

pytestmark = pytest.mark.integration


def test_checkout_prices_from_the_database_and_takes_stock_once(
    member, make_product, checkout, settings
):
    # The README's journey B: one taxable line, one not. The request lies about every price.
    settings.SALES_TAX_RATE = Decimal("0.05")
    shirt = make_product(price=Decimal("44.95"), taxable=True, quantity=5)
    mug = make_product(price=Decimal("27.95"), taxable=False, quantity=5)

    response = checkout(
        member, [(shirt, 1), (mug, 1)], total="0.01", subtotal="0.01", price="0.01"
    )

    assert response.status_code == 201, response.data
    assert Decimal(response.data["subtotal"]) == Decimal("72.90")
    assert Decimal(response.data["total_tax"]) == Decimal("2.25")
    assert Decimal(response.data["total"]) == Decimal("75.15")

    shirt.refresh_from_db()
    mug.refresh_from_db()
    assert (shirt.quantity, mug.quantity) == (4, 4)

    order = Order.objects.get(pk=response.data["id"])
    assert order.payment_status == PaymentStatus.PAID
    assert order.items.count() == 2


def test_declined_card_leaves_no_order_no_stock_change_and_no_email(
    member, product, checkout, declined_card
):
    starting_stock = product.quantity

    response = checkout(member, [(product, 2)], number=declined_card)

    assert response.status_code == 402
    assert response.data["decline_code"] == "card_declined"
    assert Order.objects.count() == 0
    product.refresh_from_db()
    assert product.quantity == starting_stock
    assert mail.outbox == []


def test_quantity_equal_to_stock_passes_and_one_over_is_refused(
    member, make_product, checkout
):
    exact = make_product(quantity=2)
    assert checkout(member, [(exact, 2)]).status_code == 201
    exact.refresh_from_db()
    assert exact.quantity == 0

    over = make_product(quantity=2)
    response = checkout(member, [(over, 3)])

    assert response.status_code == 400
    over.refresh_from_db()
    assert over.quantity == 2
    assert Order.objects.count() == 1


def test_duplicate_lines_for_one_product_collapse_into_one(
    member, product, as_user, card_payload
):
    # Two lines, same product: stock taken once for the sum, one line on the order.
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

    assert response.status_code == 201, response.data
    product.refresh_from_db()
    assert product.quantity == 5
    order = Order.objects.get(pk=response.data["id"])
    assert order.items.count() == 1
    assert order.items.first().quantity == 5


def test_order_keeps_brand_and_last4_but_never_the_card_number(
    member, product, checkout, approved_card
):
    response = checkout(member, [(product, 1)])

    assert response.status_code == 201, response.data
    assert response.data["card_brand"] == "visa"
    assert response.data["card_last4"] == approved_card[-4:]
    assert approved_card not in str(response.data)

    row = model_to_dict(Order.objects.get(pk=response.data["id"]))
    assert approved_card not in " ".join(str(v) for v in row.values())


def test_line_items_snapshot_name_and_price_at_purchase(
    member, brand, make_product, checkout
):
    # Renaming or repricing the product later must not rewrite history.
    product = make_product(name="Original name", price=Decimal("25.00"), brand=brand)
    response = checkout(member, [(product, 1)])
    assert response.status_code == 201, response.data

    product.name = "Renamed later"
    product.price = Decimal("999.00")
    product.save(update_fields=["name", "price"])

    item = Order.objects.get(pk=response.data["id"]).items.first()
    assert item.product_name == "Original name"
    assert item.brand_name == brand.name
    assert item.purchase_price == Decimal("25.00")
