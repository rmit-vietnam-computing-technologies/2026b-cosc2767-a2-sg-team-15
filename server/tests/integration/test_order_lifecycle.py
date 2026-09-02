# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every case. The one-way-door rule for a
#   cancelled line is documented in the docstring of
#   apps/orders/services.set_item_status. Reference:
#   Django REST Framework viewsets, https://www.django-rest-framework.org/api-guide/viewsets/

"""
[T15-BE-TEST][REQ-5] Integration tests: the order lifecycle after checkout.

Cancelling is where stock moves back onto the shelf and money moves back to
the customer, so it is the second place — after checkout itself — where a
mistake costs real inventory. The properties worth holding are that stock is
returned exactly once, that an order with nothing left to ship is not left
marked as paid, and that a cancelled line cannot be revived.

That last one reads like a missing feature until you work out what reviving
would have to do: take units back off a shelf that may no longer have them,
and re-charge a card that has already been refunded. Doing neither — which is
what happens if the status is simply allowed to change — leaves an order that
is "placed" and "refunded" at the same time, holding stock it already gave
back.
"""

import pytest

from apps.orders.models import Order, OrderItemStatus, OrderStatus, PaymentStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def placed_order(member, make_product, checkout):
    """An order for two different products, ready to be cancelled.

    Returns ``(order, first_product, second_product)``. Two lines rather than
    one, because partial cancellation is where the totals arithmetic is
    actually exercised.
    """
    first = make_product(name="First", price="20.00", quantity=10)
    second = make_product(name="Second", price="30.00", quantity=10)

    response = checkout(member, [(first, 2), (second, 1)])
    assert response.status_code == 201

    order = Order.objects.get(pk=response.data["id"])
    return order, first, second


# ===========================================================================
# Cancelling a whole order
# ===========================================================================


def test_cancelling_an_order_restores_stock(as_user, member, placed_order):
    """[REQ-5] Every line goes back on the shelf, once."""
    order, first, second = placed_order

    response = as_user(member).post(f"/api/orders/{order.pk}/cancel/")

    assert response.status_code == 200
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.quantity == 10
    assert second.quantity == 10


def test_cancelling_marks_the_order_cancelled_and_refunded(
    as_user, member, placed_order
):
    """An order with nothing left to ship must not still read as paid.

    A cancelled order sitting at ``payment_status = paid`` is the kind of
    inconsistency that becomes a support ticket rather than an exception.
    """
    order, _first, _second = placed_order

    as_user(member).post(f"/api/orders/{order.pk}/cancel/")

    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert order.payment_status == PaymentStatus.REFUNDED
    assert set(order.items.values_list("status", flat=True)) == {
        OrderItemStatus.CANCELLED
    }


def test_cancelling_zeroes_the_order_total(as_user, member, placed_order):
    """Totals are re-summed from the surviving lines, of which there are none."""
    order, _first, _second = placed_order

    response = as_user(member).post(f"/api/orders/{order.pk}/cancel/")

    assert response.data["subtotal"] == "0.00"
    assert response.data["total"] == "0.00"


def test_cancelling_twice_does_not_restock_twice(as_user, member, placed_order):
    """[REQ-5] Idempotence, and the most expensive bug in this file if absent.

    A double-click on the cancel button must not hand back six units for a
    two-unit line. ``cancel_order`` excludes lines that are already cancelled,
    so the second call has nothing to return.
    """
    order, first, second = placed_order

    as_user(member).post(f"/api/orders/{order.pk}/cancel/")
    as_user(member).post(f"/api/orders/{order.pk}/cancel/")

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.quantity == 10
    assert second.quantity == 10


def test_the_order_survives_cancellation(as_user, member, placed_order):
    """Cancelled, not deleted.

    The original removed the order row outright, which erased the customer's
    purchase history and made their own bookmarked order link 404.
    """
    order, _first, _second = placed_order

    as_user(member).post(f"/api/orders/{order.pk}/cancel/")

    assert Order.objects.filter(pk=order.pk).exists()
    assert as_user(member).get(f"/api/orders/{order.pk}/").status_code == 200


# ===========================================================================
# Cancelling one line
# ===========================================================================


def test_cancelling_one_line_restocks_only_that_line(as_user, member, placed_order):
    order, first, second = placed_order
    line = order.items.get(product=first)

    response = as_user(member).patch(
        f"/api/orders/{order.pk}/items/{line.pk}/",
        {"status": OrderItemStatus.CANCELLED},
        format="json",
    )

    assert response.status_code == 200
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.quantity == 10
    assert second.quantity == 9


def test_partial_cancellation_recalculates_the_total_and_keeps_the_order_live(
    as_user, member, placed_order
):
    """Something is still going out of the door, so the order stays placed."""
    order, first, _second = placed_order
    line = order.items.get(product=first)

    response = as_user(member).patch(
        f"/api/orders/{order.pk}/items/{line.pk}/",
        {"status": OrderItemStatus.CANCELLED},
        format="json",
    )

    # 2 x 20.00 cancelled, leaving 1 x 30.00.
    assert response.data["subtotal"] == "30.00"
    assert response.data["total"] == "30.00"
    order.refresh_from_db()
    assert order.status == OrderStatus.PLACED
    assert order.payment_status == PaymentStatus.PAID


def test_a_cancelled_line_cannot_be_revived(as_user, member, admin, placed_order):
    """[REQ-5] The one-way door.

    Allowing this would leave an order holding stock it already returned and
    money it already refunded. Re-ordering is the supported path, because a
    checkout handles stock and payment properly.
    """
    order, first, _second = placed_order
    line = order.items.get(product=first)

    as_user(member).patch(
        f"/api/orders/{order.pk}/items/{line.pk}/",
        {"status": OrderItemStatus.CANCELLED},
        format="json",
    )

    response = as_user(admin).patch(
        f"/api/orders/{order.pk}/items/{line.pk}/",
        {"status": OrderItemStatus.SHIPPED},
        format="json",
    )

    assert response.status_code == 400
    first.refresh_from_db()
    assert first.quantity == 10


def test_cancelling_every_line_individually_cancels_the_order(
    as_user, member, placed_order
):
    """The same end state as the whole-order cancel, reached one line at a time."""
    order, _first, _second = placed_order

    for line in order.items.all():
        as_user(member).patch(
            f"/api/orders/{order.pk}/items/{line.pk}/",
            {"status": OrderItemStatus.CANCELLED},
            format="json",
        )

    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert order.payment_status == PaymentStatus.REFUNDED


# ===========================================================================
# Who may move a line where
# ===========================================================================


def test_a_customer_may_cancel_but_not_fulfil(as_user, member, placed_order):
    """Fulfilment status is the store's to set, not the shopper's."""
    order, first, _second = placed_order
    line = order.items.get(product=first)

    response = as_user(member).patch(
        f"/api/orders/{order.pk}/items/{line.pk}/",
        {"status": OrderItemStatus.SHIPPED},
        format="json",
    )

    assert response.status_code == 403
    line.refresh_from_db()
    assert line.status == OrderItemStatus.NOT_PROCESSED


def test_an_admin_may_move_a_line_through_fulfilment(as_user, admin, placed_order):
    order, first, _second = placed_order
    line = order.items.get(product=first)

    for status_value in (
        OrderItemStatus.PROCESSING,
        OrderItemStatus.SHIPPED,
        OrderItemStatus.DELIVERED,
    ):
        response = as_user(admin).patch(
            f"/api/orders/{order.pk}/items/{line.pk}/",
            {"status": status_value},
            format="json",
        )
        assert response.status_code == 200

    line.refresh_from_db()
    assert line.status == OrderItemStatus.DELIVERED
    # Fulfilment does not touch stock; only cancellation does.
    first.refresh_from_db()
    assert first.quantity == 8


def test_fulfilment_does_not_refund_the_order(as_user, admin, placed_order):
    order, first, _second = placed_order
    line = order.items.get(product=first)

    as_user(admin).patch(
        f"/api/orders/{order.pk}/items/{line.pk}/",
        {"status": OrderItemStatus.SHIPPED},
        format="json",
    )

    order.refresh_from_db()
    assert order.status == OrderStatus.PLACED
    assert order.payment_status == PaymentStatus.PAID
    assert order.total == 70


def test_a_line_cannot_be_reached_through_someone_elses_order(
    as_user, other_member, placed_order
):
    """The item is looked up through the order, which is scoped to the caller.

    A line item id alone is not enough to reach it, which the original
    permitted.
    """
    order, first, _second = placed_order
    line = order.items.get(product=first)

    response = as_user(other_member).patch(
        f"/api/orders/{order.pk}/items/{line.pk}/",
        {"status": OrderItemStatus.CANCELLED},
        format="json",
    )

    assert response.status_code == 404
    first.refresh_from_db()
    assert first.quantity == 8


def test_the_item_route_requires_its_trailing_slash(as_user, admin, placed_order):
    """[T15-BE-NGINX] A missing slash is a 301, and a 301 loses the body.

    ``DefaultRouter`` generates this route with a trailing slash, so a PATCH
    to the slashless path is answered by Django's APPEND_SLASH redirect
    rather than by the view. Clients that do not follow redirects see a 301;
    clients that do follow one re-issue it as a GET and silently drop the
    payload, so the status change appears to succeed and nothing happens.

    Pinned here because the same trap reappears at the reverse proxy: an
    nginx location that rewrites away a trailing slash breaks exactly this
    endpoint and nothing else, which is a miserable thing to debug from a
    deployed environment.
    """
    order, first, _second = placed_order
    line = order.items.get(product=first)

    response = as_user(admin).patch(
        f"/api/orders/{order.pk}/items/{line.pk}",
        {"status": OrderItemStatus.CANCELLED},
        format="json",
    )

    assert response.status_code == 301
    line.refresh_from_db()
    assert line.status == OrderItemStatus.NOT_PROCESSED


def test_an_unknown_status_value_is_refused(as_user, admin, placed_order):
    order, first, _second = placed_order
    line = order.items.get(product=first)

    response = as_user(admin).patch(
        f"/api/orders/{order.pk}/items/{line.pk}/",
        {"status": "teleported"},
        format="json",
    )

    assert response.status_code == 400
