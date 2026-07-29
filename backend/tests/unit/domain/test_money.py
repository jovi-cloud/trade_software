"""Money and rounding policy tests."""

from __future__ import annotations

from decimal import Decimal

from app.domain.money import add_money, mul_money, round_money, to_decimal


def test_to_decimal_uses_string_conversion() -> None:
    assert to_decimal(0.1) == Decimal("0.1")


def test_round_money_six_decimal_places() -> None:
    assert round_money(1.23456789) == 1.234568


def test_mul_money_avoids_float_drift() -> None:
    assert mul_money(0.1, 0.2) == 0.02


def test_add_money_is_deterministic() -> None:
    assert add_money(1000.1, 0.2) == 1000.3
