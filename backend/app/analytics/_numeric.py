"""Rounding and division guards shared by every analytics module.

Two rules are enforced here rather than repeated in each formula:

1. **Nothing undefined is reported as a number.** A ratio with a zero
   denominator is ``None``, never 0.0 and never infinity. Zero would read as a
   real measurement ("profit factor 0" implies losses), and JSON cannot carry
   infinity or NaN at all.
2. **Everything is rounded through the project rounding policy** so a metric
   never carries float presentation noise into a saved run or a comparison.
"""

from __future__ import annotations

import math

import numpy as np

from app.analytics.equity import FloatArray
from app.domain.money import round_money, round_percent


def money(value: float) -> float:
    """Round a currency amount to the project money precision."""
    return round_money(float(value))


def money_or_none(value: float | None) -> float | None:
    """Round a currency amount that may be genuinely unmeasurable."""
    return None if value is None else money(value)


def percent(value: float) -> float:
    """Round a percentage. 12.5 means 12.5%, per the project-wide convention."""
    return round_percent(float(value))


def ratio(value: float | None) -> float | None:
    """Round a dimensionless ratio, collapsing anything non-finite to ``None``."""
    if value is None:
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    return round_money(numeric)


def divide(numerator: float, denominator: float) -> float | None:
    """``numerator / denominator``, or ``None`` when it is not defined."""
    if denominator == 0 or not math.isfinite(denominator) or not math.isfinite(numerator):
        return None
    result = numerator / denominator
    return result if math.isfinite(result) else None


def mean(values: FloatArray) -> float:
    """Arithmetic mean, 0.0 for an empty sample."""
    if values.size == 0:
        return 0.0
    return float(np.mean(values))


def sample_stdev(values: FloatArray) -> float | None:
    """Sample standard deviation (``ddof=1``).

    ``None`` below two observations, and for a perfectly flat series where the
    deviation is genuinely zero - a zero here would divide into the ratios that
    consume it, so it is reported as undefined instead.
    """
    if values.size < 2:
        return None
    deviation = float(np.std(values, ddof=1))
    if not math.isfinite(deviation) or deviation == 0.0:
        return None
    return deviation
