# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   mutation-checked every case. Reference: Python decimal module,
#   https://docs.python.org/3/library/decimal.html

"""Money and tax helpers. A cent per line, never loud, so every edge is pinned."""

from decimal import Decimal

import pytest

from apps.orders.services import money, tax_for

pytestmark = pytest.mark.unit


def test_money_rounds_half_up_at_the_cent_boundary():
    # Banker's rounding would send 10.005 to 10.00 and 2.675 to 2.68 by luck.
    table = [
        ("10.005", "10.01"),
        ("10.004", "10.00"),
        ("2.675", "2.68"),
        ("0", "0.00"),
        ("1234567.891", "1234567.89"),
    ]
    for value, expected in table:
        assert money(value) == Decimal(expected), f"{value} -> {expected}"
        assert money(value).as_tuple().exponent == -2, f"{value} keeps two places"


def test_tax_applies_only_to_taxable_lines_and_rounds_half_up(settings):
    settings.SALES_TAX_RATE = Decimal("0.05")
    # (line total, taxable, expected tax). 44.95 is the README's own worked example.
    table = [
        ("44.95", True, "2.25"),
        ("27.95", False, "0.00"),
        ("0.10", True, "0.01"),
        ("0.09", True, "0.00"),
        ("0.00", True, "0.00"),
        ("1000000.00", False, "0.00"),
    ]
    for amount, taxable, expected in table:
        assert tax_for(amount, taxable) == Decimal(expected), f"{amount} taxable={taxable}"
