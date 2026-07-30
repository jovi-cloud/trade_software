"""Trend indicators: SMA, EMA, WMA, MACD, Donchian channel, SuperTrend."""

from __future__ import annotations

from typing import ClassVar

from app.engine.bars import Bar
from app.engine.indicators.base import Indicator, RollingWindow
from app.engine.indicators.volatility import AverageTrueRange


class SimpleMovingAverage(Indicator):
    """Arithmetic mean of the last ``period`` closes.

    Formula: ``SMA_t = (1/n) * sum(close[t-n+1..t])``. Publishes nothing until
    ``n`` closes have been seen - a partial-window average is a different
    statistic and silently returning one is how off-by-one signal bugs start.
    """

    def __init__(self, period: int, *, source: str = "close") -> None:
        super().__init__()
        self._period = period
        self._source = source
        self._window = RollingWindow(period)

    @property
    def warmup_bars(self) -> int:
        return self._period

    def _compute(self, bar: Bar) -> None:
        self._window.append(_source_value(bar, self._source))
        self._publish("value", self._window.mean())


class ExponentialMovingAverage(Indicator):
    """Exponentially weighted mean with ``alpha = 2 / (period + 1)``.

    Seeded with the SMA of the first ``period`` values rather than the first
    close. Seeding from a single close makes the first few hundred EMA values
    depend on where the dataset happens to start, so two runs over overlapping
    date ranges would disagree - unacceptable when the whole point is
    reproducible comparison.
    """

    def __init__(self, period: int, *, source: str = "close") -> None:
        super().__init__()
        self._period = period
        self._source = source
        self._alpha = 2.0 / (period + 1.0)
        self._seed = RollingWindow(period)
        self._current: float | None = None

    @property
    def warmup_bars(self) -> int:
        return self._period

    def _compute(self, bar: Bar) -> None:
        value = _source_value(bar, self._source)
        if self._current is None:
            self._seed.append(value)
            self._current = self._seed.mean()
        else:
            self._current = self._current + self._alpha * (value - self._current)
        self._publish("value", self._current)


class WeightedMovingAverage(Indicator):
    """Linearly weighted mean: the newest close carries weight ``n``, the oldest ``1``."""

    def __init__(self, period: int, *, source: str = "close") -> None:
        super().__init__()
        self._period = period
        self._source = source
        self._window = RollingWindow(period)
        self._denominator = period * (period + 1) / 2.0

    @property
    def warmup_bars(self) -> int:
        return self._period

    def _compute(self, bar: Bar) -> None:
        self._window.append(_source_value(bar, self._source))
        if not self._window.is_full:
            self._publish("value", None)
            return
        weighted = sum(value * (index + 1) for index, value in enumerate(self._window.items))
        self._publish("value", weighted / self._denominator)


class Macd(Indicator):
    """Moving Average Convergence Divergence.

    ``line = EMA(fast) - EMA(slow)``, ``signal = EMA(signal_period)`` of the
    line, ``histogram = line - signal``. The signal EMA is only fed once the
    line exists, so its own seeding window starts at the first valid line
    value - which is why total warmup is ``slow + signal - 1``, not
    ``slow + signal``.
    """

    outputs: ClassVar[tuple[str, ...]] = ("line", "signal", "histogram")

    def __init__(self, fast_period: int, slow_period: int, signal_period: int) -> None:
        super().__init__()
        self._fast = ExponentialMovingAverage(fast_period)
        self._slow = ExponentialMovingAverage(slow_period)
        self._signal_period = signal_period
        self._signal_seed = RollingWindow(signal_period)
        self._signal_alpha = 2.0 / (signal_period + 1.0)
        self._signal: float | None = None
        self._slow_period = slow_period

    @property
    def warmup_bars(self) -> int:
        return self._slow_period + self._signal_period - 1

    def _compute(self, bar: Bar) -> None:
        self._fast.update(bar)
        self._slow.update(bar)
        fast, slow = self._fast.value, self._slow.value
        if fast is None or slow is None:
            self._publish_all(line=None, signal=None, histogram=None)
            return

        line = fast - slow
        if self._signal is None:
            self._signal_seed.append(line)
            self._signal = self._signal_seed.mean()
        else:
            self._signal = self._signal + self._signal_alpha * (line - self._signal)

        signal = self._signal
        self._publish_all(
            line=line,
            signal=signal,
            histogram=None if signal is None else line - signal,
        )


class DonchianChannel(Indicator):
    """Highest high and lowest low over ``period`` bars.

    ``exclude_current`` shifts the channel back one bar, which is what a
    breakout rule almost always wants: "is this bar's high above the *prior*
    N-bar high" is a signal, whereas comparing a bar's high against a channel
    that already includes it is trivially true at every new extreme.
    """

    outputs: ClassVar[tuple[str, ...]] = ("upper", "lower", "middle", "width")

    def __init__(self, period: int, *, exclude_current: bool = False) -> None:
        super().__init__()
        self._period = period
        self._exclude_current = exclude_current
        self._highs = RollingWindow(period)
        self._lows = RollingWindow(period)

    @property
    def warmup_bars(self) -> int:
        return self._period + (1 if self._exclude_current else 0)

    def _compute(self, bar: Bar) -> None:
        if self._exclude_current:
            self._publish_from_window()
            self._highs.append(bar.high)
            self._lows.append(bar.low)
            return
        self._highs.append(bar.high)
        self._lows.append(bar.low)
        self._publish_from_window()

    def _publish_from_window(self) -> None:
        if not self._highs.is_full:
            self._publish_all(upper=None, lower=None, middle=None, width=None)
            return
        upper = self._highs.highest()
        lower = self._lows.lowest()
        assert upper is not None and lower is not None
        self._publish_all(
            upper=upper,
            lower=lower,
            middle=(upper + lower) / 2.0,
            width=upper - lower,
        )


class SuperTrend(Indicator):
    """ATR-banded trend follower.

    Uses the widely published formulation::

        hl2   = (high + low) / 2
        upper = hl2 + multiplier * ATR(period)
        lower = hl2 - multiplier * ATR(period)
        lower := close[1] > lower[1] ? max(lower, lower[1]) : lower
        upper := close[1] < upper[1] ? min(upper, upper[1]) : upper
        direction := close > upper[1] ? +1 : close < lower[1] ? -1 : direction[1]
        value = direction > 0 ? lower : upper

    The bands only ever ratchet in the direction of the trend, which is what
    makes the line act as a trailing stop. ``direction`` is published as +1.0
    for uptrend and -1.0 for downtrend so it can flow through the same
    float-valued indicator channel as everything else.
    """

    outputs: ClassVar[tuple[str, ...]] = ("value", "direction", "upper", "lower")

    def __init__(self, period: int, multiplier: float) -> None:
        super().__init__()
        self._atr = AverageTrueRange(period)
        self._multiplier = multiplier
        self._period = period
        self._prev_upper: float | None = None
        self._prev_lower: float | None = None
        self._prev_close: float | None = None
        self._direction = 1.0

    @property
    def warmup_bars(self) -> int:
        return self._period + 1

    def _compute(self, bar: Bar) -> None:
        self._atr.update(bar)
        atr = self._atr.value
        if atr is None:
            self._prev_close = bar.close
            self._publish_all(value=None, direction=None, upper=None, lower=None)
            return

        hl2 = (bar.high + bar.low) / 2.0
        upper = hl2 + self._multiplier * atr
        lower = hl2 - self._multiplier * atr

        if self._prev_upper is not None and self._prev_lower is not None:
            prev_close = self._prev_close
            assert prev_close is not None
            if prev_close > self._prev_lower:
                lower = max(lower, self._prev_lower)
            if prev_close < self._prev_upper:
                upper = min(upper, self._prev_upper)

            if bar.close > self._prev_upper:
                self._direction = 1.0
            elif bar.close < self._prev_lower:
                self._direction = -1.0

        self._prev_upper, self._prev_lower = upper, lower
        self._prev_close = bar.close
        self._publish_all(
            value=lower if self._direction > 0 else upper,
            direction=self._direction,
            upper=upper,
            lower=lower,
        )


def _source_value(bar: Bar, source: str) -> float:
    """Resolve a named price source on a bar."""
    match source:
        case "close":
            return bar.close
        case "open":
            return bar.open
        case "high":
            return bar.high
        case "low":
            return bar.low
        case "hl2":
            return (bar.high + bar.low) / 2.0
        case "hlc3":
            return (bar.high + bar.low + bar.close) / 3.0
        case "ohlc4":
            return (bar.open + bar.high + bar.low + bar.close) / 4.0
        case _:
            raise ValueError(
                f"Unknown price source '{source}'; "
                "expected close, open, high, low, hl2, hlc3 or ohlc4"
            )
