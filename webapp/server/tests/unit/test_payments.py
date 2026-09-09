# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every case. Card numbers and expected
#   decline codes are taken from the module docstring in
#   server/apps/orders/payments.py. References:
#   Luhn algorithm, ISO/IEC 7812-1
#   pytest parametrize, https://docs.pytest.org/en/stable/how-to/parametrize.html

"""
[T15-BE-TEST][REQ-5] Unit tests: the payment gateway in isolation.

``apps/orders/payments.py`` is the cleanest unit-test target in the codebase.
No network, no database, no clock except where injected — every function is
pure input to output, so a failure here can only mean the logic is wrong.

Two properties are worth stating because they are what make these tests cheap
enough to run on every commit and every deployment: the gateway is simulated,
so there is no provider, account, key or outbound call; and a declined card
leaves no order and takes no stock, so the decline numbers are safe to fire
repeatedly from CI and from a post-deploy check on a private subnet.
"""

import dataclasses
import logging
from datetime import date

import pytest
from freezegun import freeze_time

from apps.orders.payments import (
    APPROVE_CARDS,
    DECLINE_CARDS,
    Charge,
    PaymentDeclined,
    authorise,
    card_brand,
    cvc_length_for,
    has_expired,
    luhn_valid,
    normalise,
)

pytestmark = pytest.mark.unit

# A date far enough out that these tests do not rot, used wherever the expiry
# is meant to be irrelevant to what the test is actually checking.
FUTURE = {"exp_month": 12, "exp_year": 2099}


# ===========================================================================
# normalise
# ===========================================================================


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("4242424242424242", "4242424242424242"),
        ("4242 4242 4242 4242", "4242424242424242"),
        ("4242-4242-4242-4242", "4242424242424242"),
        ("  4242 4242-4242 4242  ", "4242424242424242"),
        ("3782 822463 10005", "378282246310005"),
        (4242424242424242, "4242424242424242"),
        ("", ""),
        ("not a card", ""),
    ],
)
def test_normalise_keeps_only_digits(raw, expected):
    """Card fields receive whatever the shopper typed, spacing included."""
    assert normalise(raw) == expected


# ===========================================================================
# luhn_valid
# ===========================================================================


@pytest.mark.parametrize("number", sorted(APPROVE_CARDS))
def test_every_documented_approve_card_passes_luhn(number):
    assert luhn_valid(number) is True


@pytest.mark.parametrize("number", sorted(DECLINE_CARDS))
def test_every_documented_decline_card_passes_luhn(number):
    """Declines are valid numbers that the gateway refuses.

    Worth asserting explicitly: a decline is a payment outcome, not a typo.
    If these failed the Luhn check the serializer would reject them at the
    boundary and ``authorise`` would never see them, so the decline paths
    would be untestable through the API.
    """
    assert luhn_valid(number) is True


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        ("4242424242424242", True),
        ("4242424242424241", False),   # one digit changed
        ("4242424242424242".replace("24", "42", 1), False),  # transposition
        ("400000000002", True),        # 12 digits, the lower bound
        ("40000000006", False),        # 11 digits, below the bound
        ("4000000000000000006", True),  # 19 digits, the upper bound
        ("40000000000000000002", False),  # 20 digits, above the bound
        ("", False),
        ("abcdefgh", False),
        ("4242 4242 4242 4242", True),  # spacing must not matter
    ],
)
def test_luhn_valid(number, expected):
    """Length bounds are 12 to 19 inclusive.

    The out-of-range numbers here are genuinely Luhn-correct — they are
    rejected for their length alone, which is what makes them the right cases
    to pin the boundary with.
    """
    assert luhn_valid(number) is expected


# ===========================================================================
# card_brand
# ===========================================================================


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        ("4242424242424242", "visa"),
        ("4000056655665556", "visa"),
        ("4", "visa"),                  # single digit, before `two` is readable
        ("378282246310005", "amex"),    # 37
        ("341449635398431", "amex"),    # 34
        ("5555555555554444", "mastercard"),   # 55
        ("5105105105105100", "mastercard"),   # 51
        ("2221000000000009", "mastercard"),   # newer range, lower edge
        ("2720000000000005", "mastercard"),   # newer range, upper edge
        ("2220000000000000", "card"),   # one below the newer range
        ("2721000000000000", "card"),   # one above the newer range
        ("3530111333300000", "jcb"),    # 35
        ("6011111111111117", "discover"),
        ("6500000000000002", "discover"),
        ("9999999999999999", "card"),   # unknown issuer
        ("", "card"),
    ],
)
def test_card_brand(number, expected):
    """Brand comes from the leading digits, the way a payment form does it.

    The two Mastercard ranges and their edges are the cases that matter.
    Mastercard owns both the old 51-55 prefix and the newer 2221-2720 one, and
    an off-by-one there shows up as a card that silently loses its brand — the
    charge still succeeds, so nothing fails loudly, and the wrong logo appears
    on the receipt.
    """
    assert card_brand(number) == expected


@pytest.mark.parametrize("number", sorted(APPROVE_CARDS))
def test_documented_brands_match_the_lookup_table(number):
    """The module documents a brand per approve card. Prove it agrees."""
    assert card_brand(number) == APPROVE_CARDS[number]


# ===========================================================================
# cvc_length_for
# ===========================================================================


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        ("378282246310005", 4),   # amex
        ("371449635398431", 4),   # amex
        ("4242424242424242", 3),  # visa
        ("5555555555554444", 3),  # mastercard
        ("3530111333300000", 3),  # jcb
        ("", 3),                  # unknown falls back to three
    ],
)
def test_cvc_length_for(number, expected):
    assert cvc_length_for(number) == expected


# ===========================================================================
# has_expired
# ===========================================================================


@pytest.mark.parametrize(
    ("exp_month", "exp_year", "expected"),
    [
        (6, 2026, False),   # the current month is still valid
        (7, 2026, False),   # next month
        (12, 2026, False),
        (1, 2027, False),
        (5, 2026, True),    # last month
        (12, 2025, True),   # last year
        (7, 2025, True),    # a later month, but an earlier year
    ],
)
def test_has_expired_against_an_injected_date(exp_month, exp_year, expected):
    """A card is good until the last day of its expiry month.

    ``today`` is injected rather than frozen, so this reads as a table of
    dates rather than a table of dates plus a patched clock. The 6/2026 case
    is the one that matters — a card expiring this month is still valid, and
    an implementation using ``<=`` instead of ``<`` would decline it for a
    whole month.

    The 7/2025 row guards the comparison order: comparing month before year
    would call that card current.
    """
    today = date(2026, 6, 15)
    assert has_expired(exp_month, exp_year, today=today) is expected


@pytest.mark.parametrize(
    ("exp_month", "exp_year"),
    [("5", "2026"), (5, "2026"), ("5", 2026)],
)
def test_has_expired_accepts_strings(exp_month, exp_year):
    """Values arrive from JSON, so both forms have to work."""
    assert has_expired(exp_month, exp_year, today=date(2026, 6, 15)) is True


def test_has_expired_defaults_to_today():
    """With no injected date it reads the system clock."""
    with freeze_time("2026-06-15"):
        assert has_expired(5, 2026) is True
        assert has_expired(6, 2026) is False


# ===========================================================================
# authorise — approvals
# ===========================================================================


@pytest.mark.parametrize("number", sorted(APPROVE_CARDS))
def test_every_documented_approve_card_is_usable(number):
    """Assert the docstring rather than trusting it.

    The module lists these as approved. If one stopped working, checkout would
    break for anyone following the documentation, and nothing else in the
    suite would notice.
    """
    cvc = "1234" if cvc_length_for(number) == 4 else "123"
    charge = authorise(number, cvc=cvc, amount="99.95", **FUTURE)

    assert isinstance(charge, Charge)
    assert charge.brand == APPROVE_CARDS[number]
    assert charge.last4 == number[-4:]
    assert charge.amount == "99.95"


def test_an_undocumented_card_is_approved():
    """Any number not in the decline table authorises.

    Deliberate — it lets someone invent a card and still complete a purchase.
    Worth pinning so a future change to the decline logic cannot quietly turn
    the default into a refusal.
    """
    charge = authorise("4111111111111111", cvc="123", amount="10.00", **FUTURE)
    assert charge.brand == "visa"
    assert charge.last4 == "1111"


def test_charge_reference_looks_like_a_gateway_reference():
    charge = authorise("4242424242424242", cvc="123", amount="1.00", **FUTURE)
    assert charge.reference.startswith("ch_")
    assert len(charge.reference) == 27          # "ch_" plus 24 hex characters
    assert charge.reference[3:].isalnum()


def test_two_charges_get_different_references():
    a = authorise("4242424242424242", cvc="123", amount="1.00", **FUTURE)
    b = authorise("4242424242424242", cvc="123", amount="1.00", **FUTURE)
    assert a.reference != b.reference


def test_spacing_in_the_number_is_tolerated():
    charge = authorise("4242 4242 4242 4242", cvc="123", amount="1.00", **FUTURE)
    assert charge.brand == "visa"
    assert charge.last4 == "4242"


# ===========================================================================
# authorise — the card number must not survive
# ===========================================================================


def test_charge_carries_no_card_number():
    """[REQ-5] The PAN is never stored, never returned.

    Same rule a real integration works under: keep the brand and the last four
    digits, discard everything else. This asserts it against every field of
    the returned object rather than the ones we happen to remember.
    """
    number = "4242424242424242"
    charge = authorise(number, cvc="123", amount="99.95", **FUTURE)

    for field in dataclasses.fields(Charge):
        value = str(getattr(charge, field.name))
        assert number not in value, f"Charge.{field.name} leaked the card number"
        assert number[:12] not in value, f"Charge.{field.name} leaked most of it"


def test_the_card_number_is_never_logged(caplog):
    """A log aggregator ships whatever the process prints.

    Requirement 4's log aggregation means anything logged here ends up in a
    searchable store, so a PAN in a log line is a PAN in a database nobody
    treats as sensitive.
    """
    number = "4242424242424242"
    with caplog.at_level(logging.DEBUG, logger="apps.orders.payments"):
        authorise(number, cvc="123", amount="99.95", **FUTURE)

    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert number not in combined
    assert "4242" in combined, "the last four digits should still be logged"


def test_charge_is_immutable():
    """Frozen, so nothing downstream can rewrite the amount after the fact."""
    charge = authorise("4242424242424242", cvc="123", amount="99.95", **FUTURE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        charge.amount = "0.01"


# ===========================================================================
# authorise — declines
# ===========================================================================


@pytest.mark.parametrize("number", sorted(DECLINE_CARDS))
def test_every_documented_decline_card_is_refused(number):
    expected_code, expected_message = DECLINE_CARDS[number]

    with pytest.raises(PaymentDeclined) as excinfo:
        authorise(number, cvc="123", amount="99.95", **FUTURE)

    assert excinfo.value.decline_code == expected_code
    assert expected_message in str(excinfo.value)


def test_a_decline_is_402_not_400():
    """[REQ-5] The status code carries meaning the SPA depends on.

    400 means the request was malformed — fix your typo. 402 means the request
    was fine and the payment failed — try a different card. Collapsing the two
    leaves the shopper with no idea which they are looking at.
    """
    from rest_framework import status

    with pytest.raises(PaymentDeclined) as excinfo:
        authorise("4000000000000002", cvc="123", amount="1.00", **FUTURE)

    assert excinfo.value.status_code == status.HTTP_402_PAYMENT_REQUIRED


def test_expired_card_is_declined():
    with freeze_time("2026-06-15"):
        with pytest.raises(PaymentDeclined) as excinfo:
            authorise("4242424242424242", exp_month=5, exp_year=2026,
                      cvc="123", amount="1.00")
    assert excinfo.value.decline_code == "expired_card"


def test_a_card_expiring_this_month_still_authorises():
    """The boundary, exercised through authorise rather than has_expired."""
    with freeze_time("2026-06-15"):
        charge = authorise("4242424242424242", exp_month=6, exp_year=2026,
                           cvc="123", amount="1.00")
    assert charge.last4 == "4242"


@pytest.mark.parametrize(
    ("number", "cvc"),
    [
        ("4242424242424242", "12"),      # visa, too short
        ("4242424242424242", "1234"),    # visa, amex-length code
        ("5555555555554444", "12345"),   # mastercard, too long
        ("378282246310005", "123"),      # amex needs four
        ("378282246310005", "12345"),    # amex, too long
        ("4242424242424242", ""),        # empty
    ],
)
def test_wrong_length_security_code_is_declined(number, cvc):
    with pytest.raises(PaymentDeclined) as excinfo:
        authorise(number, cvc=cvc, amount="1.00", **FUTURE)
    assert excinfo.value.decline_code == "incorrect_cvc"


@pytest.mark.parametrize(
    ("number", "cvc"),
    [("378282246310005", "1234"), ("4242424242424242", "123")],
)
def test_correct_length_security_code_is_accepted(number, cvc):
    assert authorise(number, cvc=cvc, amount="1.00", **FUTURE) is not None


def test_the_decline_table_is_checked_before_the_expiry_date():
    """Order of checks, pinned.

    ``4000000000000069`` is the documented expired-card decline. Presented
    with a *valid* future expiry it must still be refused, and with its own
    code — the number is what decides, not the date. Reversing the two checks
    would make this card authorise, and the documented behaviour would
    silently stop being true.
    """
    with pytest.raises(PaymentDeclined) as excinfo:
        authorise("4000000000000069", cvc="123", amount="1.00", **FUTURE)
    assert excinfo.value.decline_code == "expired_card"

    with freeze_time("2026-06-15"):
        with pytest.raises(PaymentDeclined) as excinfo:
            authorise("4000000000009995", exp_month=1, exp_year=2020,
                      cvc="123", amount="1.00")
    assert excinfo.value.decline_code == "insufficient_funds"


def test_authorise_does_not_repeat_the_luhn_check():
    """Documents where validation actually lives.

    ``authorise`` accepts a Luhn-invalid number. That is not a defect: the
    check digit is a form-level concern and ``PaymentSerializer.validate_number``
    enforces it at the API boundary, so a bad number never reaches here.

    Pinning it means the division of responsibility is written down. If
    somebody later removes the serializer validation, the integration test for
    a malformed card fails and this test explains why the gateway did not
    catch it.
    """
    assert luhn_valid("4242424242424241") is False
    charge = authorise("4242424242424241", cvc="123", amount="1.00", **FUTURE)
    assert charge.last4 == "4241"
