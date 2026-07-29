"""Money arithmetic at fill and reporting boundaries (ARCHITECTURE.md 9).

All cash, P&L, commission, and slippage calculations use ``Decimal`` internally
to avoid binary floating-point drift. Values are converted back to ``float`` at
module boundaries so the engine API stays unchanged.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.rounding import MONEY_DECIMALS, PERCENT_DECIMALS, PRICE_DECIMALS, QUANTITY_DECIMALS


def to_decimal(value: float | int | str | Decimal) -> Decimal:
    """Convert a numeric input to Decimal without float binary artefacts."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize(value: Decimal, digits: int) -> Decimal:
    quantizer = Decimal("1").scaleb(-digits)
    return value.quantize(quantizer, rounding=ROUND_HALF_UP)


def round_decimal(value: Decimal, *, digits: int) -> Decimal:
    return _quantize(value, digits)


def round_money(value: float, digits: int = MONEY_DECIMALS) -> float:
    """Round a monetary value to avoid float noise in cash and P&L."""
    return float(_quantize(to_decimal(value), digits))


def round_price(value: float, digits: int = PRICE_DECIMALS) -> float:
    return float(_quantize(to_decimal(value), digits))


def round_quantity(value: float, digits: int = QUANTITY_DECIMALS) -> float:
    return float(_quantize(to_decimal(value), digits))


def round_percent(value: float, digits: int = PERCENT_DECIMALS) -> float:
    return float(_quantize(to_decimal(value), digits))


def add_money(left: float, right: float) -> float:
    return round_money(float(to_decimal(left) + to_decimal(right)))


def sub_money(left: float, right: float) -> float:
    return round_money(float(to_decimal(left) - to_decimal(right)))


def mul_money(left: float, right: float) -> float:
    return round_money(float(to_decimal(left) * to_decimal(right)))
