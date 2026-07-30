"""Volume indicators: session-anchored VWAP, rolling VWAP, OBV."""

from __future__ import annotations

from typing import ClassVar

from app.engine.bars import Bar
from app.engine.indicators.base import Indicator, RollingWindow
from app.engine.indicators.session import SessionClock


def typical_price(bar: Bar) -> float:
    """``(high + low + close) / 3`` - the price VWAP is conventionally built on."""
    return (bar.high + bar.low + bar.close) / 3.0


class SessionVwap(Indicator):
    """Volume-weighted average price, re-anchored at each session open.

    ``VWAP = sum(typical_price * volume) / sum(volume)`` accumulated from the
    first bar of the local session. Anchoring matters: a VWAP that never resets
    converges to a long-run average and stops being the intraday reference
    level traders actually use.

    ``distance_pct`` is the close's signed distance from VWAP in percent (2.5
    means 2.5% above), so mean-reversion rules compare a scale-free number
    instead of a price difference that means something different on every
    instrument.
    """

    outputs: ClassVar[tuple[str, ...]] = ("value", "distance_pct", "session_volume")

    def __init__(self, timezone: str) -> None:
        super().__init__()
        self._clock = SessionClock(timezone)
        self._price_volume = 0.0
        self._volume = 0.0

    @property
    def warmup_bars(self) -> int:
        return 1

    @property
    def clock(self) -> SessionClock:
        return self._clock

    def _compute(self, bar: Bar) -> None:
        if self._clock.advance(bar):
            self._price_volume = 0.0
            self._volume = 0.0

        self._price_volume += typical_price(bar) * bar.volume
        self._volume += bar.volume

        # Zero-volume bars are legal in the canonical schema (volume is
        # nullable), so fall back to the unweighted typical price rather than
        # dividing by zero or publishing nothing.
        value = typical_price(bar) if self._volume <= 0 else self._price_volume / self._volume

        self._publish_all(
            value=value,
            distance_pct=0.0 if value == 0 else (bar.close - value) / value * 100.0,
            session_volume=self._volume,
        )


class RollingVwap(Indicator):
    """VWAP over a fixed ``period`` of bars, for instruments without sessions."""

    outputs: ClassVar[tuple[str, ...]] = ("value", "distance_pct")

    def __init__(self, period: int) -> None:
        super().__init__()
        self._period = period
        self._price_volume = RollingWindow(period)
        self._volume = RollingWindow(period)

    @property
    def warmup_bars(self) -> int:
        return self._period

    def _compute(self, bar: Bar) -> None:
        self._price_volume.append(typical_price(bar) * bar.volume)
        self._volume.append(bar.volume)
        if not self._volume.is_full:
            self._publish_all(value=None, distance_pct=None)
            return

        total_volume = self._volume.total
        value = typical_price(bar) if total_volume <= 0 else self._price_volume.total / total_volume
        self._publish_all(
            value=value,
            distance_pct=0.0 if value == 0 else (bar.close - value) / value * 100.0,
        )


class OnBalanceVolume(Indicator):
    """Running total of volume signed by the direction of the close."""

    def __init__(self) -> None:
        super().__init__()
        self._total = 0.0
        self._previous_close: float | None = None

    @property
    def warmup_bars(self) -> int:
        return 2

    def _compute(self, bar: Bar) -> None:
        previous = self._previous_close
        self._previous_close = bar.close
        if previous is None:
            self._publish("value", None)
            return
        if bar.close > previous:
            self._total += bar.volume
        elif bar.close < previous:
            self._total -= bar.volume
        self._publish("value", self._total)
