# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every case. Rounding behaviour verified
#   against the Python decimal module. References:
#   decimal — Decimal fixed point arithmetic, https://docs.python.org/3/library/decimal.html
#   pytest-django settings fixture, https://pytest-django.readthedocs.io/en/latest/helpers.html

"""
Unit tests: server-side money and tax.

``money()`` and ``tax_for()`` are two short functions, which makes it tempting
to skip them. They are the two places a rounding rule can be wrong by a cent
per line and nothing will ever fail loudly — the store just quietly charges the
wrong amount, and the first report comes from a customer.

No database. ``tax_for`` reads ``settings.SALES_TAX_RATE``, so the rate is
overridden per test rather than assumed.
"""

from decimal import Decimal

import pytest

from apps.orders.services import CENTS, ZERO, money, tax_for

pytestmark = pytest.mark.unit


# ===========================================================================
# money
# ===========================================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10", "10.00"),
        ("10.1", "10.10"),
        ("10.005", "10.01"),
        ("0", "0.00"),
        ("99.95", "99.95"),
        ("1234567.891", "1234567.89"),
    ],
)
def test_money_always_returns_two_decimal_places(value, expected):
    assert money(value) == Decimal(expected)
    assert money(value).as_tuple().exponent == CENTS.as_tuple().exponent


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.005", "0.01"),   # banker's rounding would give 0.00
        ("0.015", "0.02"),
        ("0.025", "0.03"),   # banker's rounding would give 0.02
        ("0.035", "0.04"),
        ("2.675", "2.68"),   # the textbook rounding example
        ("0.004", "0.00"),   # below the halfway point, still rounds down
        ("0.006", "0.01"),
    ],
)
def test_money_rounds_half_up_not_half_even(value, expected):
    """The rounding rule, pinned.

    Python's default for ``Decimal.quantize`` is ROUND_HALF_EVEN — banker's
    rounding — which sends exact halves to the nearest even digit. A till
    rounds half *up*. The 0.005 and 0.025 cases are the ones that
    distinguish them, and each is a one-cent difference that no test would
    catch unless it looked for exactly this.
    """
    assert money(value) == Decimal(expected)


def test_money_on_a_float_is_not_the_same_as_on_a_string():
    """Why prices are never floats.

    ``Decimal(2.675)`` captures the binary approximation the float already is,
    which is slightly below 2.675, so half-up rounding takes it *down* to 2.67.
    ``Decimal("2.675")`` is exactly 2.675 and rounds up to 2.68.

    A one-cent discrepancy per line, appearing only for some values, is close
    to undebuggable in production. The model stores ``price`` as a
    DecimalField precisely so this cannot happen — this test documents what
    the alternative would silently cost.
    """
    assert money("2.675") == Decimal("2.68")
    assert money(2.675) == Decimal("2.67")


@pytest.mark.parametrize("value", [Decimal("10.005"), "10.005", 10])
def test_money_accepts_decimal_string_and_int(value):
    assert money(value) == money(Decimal(str(value)))


# ===========================================================================
# tax_for
# ===========================================================================


@pytest.mark.parametrize("amount", ["0.00", "10.00", "99.95", "1000000.00"])
def test_no_tax_on_a_product_that_is_not_taxable(amount):
    """Tax applies per product, not per order.

    ``Product.taxable`` defaults to False, so most of the catalogue is exempt
    and this is the common path rather than an edge case.
    """
    assert tax_for(amount, taxable=False) == ZERO


@pytest.mark.parametrize(
    ("amount", "rate", "expected"),
    [
        ("100.00", 0.05, "5.00"),
        ("99.95", 0.05, "5.00"),      # 4.9975, rounds up
        ("19.99", 0.05, "1.00"),      # 0.9995, rounds up
        ("10.00", 0.10, "1.00"),
        ("10.00", 0.0, "0.00"),       # a zero rate is not the same as exempt
        ("0.00", 0.05, "0.00"),
        ("0.10", 0.05, "0.01"),       # 0.005 exactly, must round up
    ],
)
def test_tax_is_the_rate_applied_and_rounded(settings, amount, rate, expected):
    settings.SALES_TAX_RATE = rate
    assert tax_for(amount, taxable=True) == Decimal(expected)


def test_tax_reads_the_rate_from_settings(settings):
    """The rate is configuration, not code.

    ``SALES_TAX_RATE`` comes from the environment, so staging and production
    can differ without a rebuild. That also means a deployment can ship the
    wrong rate with nothing failing — hence a test that changes it and watches
    the result move.
    """
    settings.SALES_TAX_RATE = 0.05
    assert tax_for("100.00", taxable=True) == Decimal("5.00")

    settings.SALES_TAX_RATE = 0.20
    assert tax_for("100.00", taxable=True) == Decimal("20.00")


def test_tax_result_is_always_two_decimal_places(settings):
    settings.SALES_TAX_RATE = 0.0825
    result = tax_for("13.37", taxable=True)
    assert result.as_tuple().exponent == CENTS.as_tuple().exponent


def test_tax_accepts_a_decimal_amount(settings):
    """Line totals arrive as Decimal from the model, not as strings."""
    settings.SALES_TAX_RATE = 0.05
    assert tax_for(Decimal("100.00"), taxable=True) == Decimal("5.00")
