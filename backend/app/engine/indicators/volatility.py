"""Volatility indicators: True Range, ATR, standard deviation, Bollinger Bands."""

from __future__ import annotations

import math
from typing import ClassVar

from app.engine.bars import Bar
from app.engine.indicators.base import Indicator, RollingWindow


def true_range(bar: Bar, previous_close: float | None) -> float:
    """Wilder's True Range.

    ``max(high - low, |high - prev_close|, |low - prev_close|)``. On the first
    bar there is no previous close, so it degrades to the bar's own range -
    the standard treatment, and the reason ATR needs one extra warmup bar
    beyond its period to be fully seeded.
    """
    if previous_close is None:
        return bar.high - bar.low
    return max(
        bar.high - bar.low,
        abs(bar.high - previous_close),
        abs(bar.low - previous_close),
    )


class AverageTrueRange(Indicator):
    """Wilder-smoothed True Range.

    Seeded with the arithmetic mean of the first ``period`` true ranges, then
    smoothed as ``ATR_t = (ATR_{t-1} * (n-1) + TR_t) / n``. This is Wilder's
    original recursion, not an EMA with ``alpha = 2/(n+1)`` - they differ, and
    stop distances computed from the wrong one are quietly wider or tighter
    than intended.
    """

    def __init__(self, period: int) -> None:
        super().__init__()
        self._period = period
        self._seed = RollingWindow(period)
        self._current: float | None = None
        self._previous_close: float | None = None

    @property
    def warmup_bars(self) -> int:
        return self._period + 1

    def _compute(self, bar: Bar) -> None:
        tr = true_range(bar, self._previous_close)
        self._previous_close = bar.close

        if self._current is None:
            self._seed.append(tr)
            self._current = self._seed.mean()
        else:
            self._current = (self._current * (self._period - 1) + tr) / self._period
        self._publish("value", self._current)


class StandardDeviation(Indicator):
    """Population standard deviation of the last ``period`` closes (ddof=0).

    Population rather than sample, because that is the convention Bollinger
    Bands were defined with; using the sample form would widen every band.
    """

    def __init__(self, period: int) -> None:
        super().__init__()
        self._period = period
        self._window = RollingWindow(period)

    @property
    def warmup_bars(self) -> int:
        return self._period

    def _compute(self, bar: Bar) -> None:
        self._window.append(bar.close)
        variance = self._window.variance()
        self._publish("value", None if variance is None else math.sqrt(variance))


class BollingerBands(Indicator):
    """SMA envelope at ``+/- k`` population standard deviations.

    ``percent_b`` places the close inside the envelope (0 at the lower band, 1
    at the upper); ``bandwidth`` is ``(upper - lower) / middle``, the standard
    squeeze measure. Both are published because computing them in strategy
    code would put arithmetic where Part 1 says only conditions belong.
    """

    outputs: ClassVar[tuple[str, ...]] = (
        "middle",
        "upper",
        "lower",
        "bandwidth",
        "percent_b",
    )

    def __init__(self, period: int, deviations: float) -> None:
        super().__init__()
        self._period = period
        self._deviations = deviations
        self._window = RollingWindow(period)

    @property
    def warmup_bars(self) -> int:
        return self._period

    def _compute(self, bar: Bar) -> None:
        self._window.append(bar.close)
        middle = self._window.mean()
        variance = self._window.variance()
        if middle is None or variance is None:
            self._publish_all(middle=None, upper=None, lower=None, bandwidth=None, percent_b=None)
            return

        deviation = math.sqrt(variance)
        upper = middle + self._deviations * deviation
        lower = middle - self._deviations * deviation
        span = upper - lower
        self._publish_all(
            middle=middle,
            upper=upper,
            lower=lower,
            bandwidth=0.0 if middle == 0 else span / middle,
            # A zero-width band means every close sits exactly on the mean;
            # 0.5 is the only reading consistent with that.
            percent_b=0.5 if span == 0 else (bar.close - lower) / span,
        )
