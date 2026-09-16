# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Drafted with Claude (Anthropic); the author ran and
#   mutation-checked every case. Card numbers are the upstream module's own
#   documented test set. Reference: Luhn algorithm,
#   https://en.wikipedia.org/wiki/Luhn_algorithm

"""Card checks in isolation. No network, no database, clock injected."""

from datetime import date

import pytest

from apps.orders.payments import has_expired, luhn_valid

pytestmark = pytest.mark.unit


def test_luhn_accepts_and_rejects_at_the_length_and_checksum_edges():
    # Length bounds are 12 to 19 digits; the out-of-range numbers are otherwise valid.
    table = [
        ("4242424242424242", True),
        ("4242424242424241", False),
        ("4242 4242 4242 4242", True),
        ("400000000002", True),
        ("40000000006", False),
        ("4000000000000000006", True),
        ("40000000000000000002", False),
        ("", False),
    ]
    for number, expected in table:
        assert luhn_valid(number) is expected, f"{number!r} ({len(number)} chars)"


def test_card_is_valid_until_the_last_day_of_its_expiry_month():
    today = date(2026, 6, 15)
    # (month, year, expired). 7/2025 guards the compare order: later month, earlier year.
    table = [
        (6, 2026, False),
        (7, 2026, False),
        (5, 2026, True),
        (12, 2025, True),
        (7, 2025, True),
        ("6", "2026", False),
    ]
    for month, year, expected in table:
        assert has_expired(month, year, today=today) is expected, f"{month}/{year}"
