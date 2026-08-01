"""Production trailing stop loss management.

Trailing stops ratchet in the profitable direction only. On each bar the
favourable extreme is updated first (high for longs, low for shorts), the stop
level is recomputed, then the bar range is checked for a breach.

Percent trails are measured from the best price reached. Points trails subtract
a fixed price distance. ATR trails use the current bar's ATR when available and
fall back to the ATR captured at entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.enums import PositionSide
from app.engine.bars import Bar


class TrailingMethod(StrEnum):
    """Exactly one trailing distance model may be active."""

    PERCENT = "percent"
    POINTS = "points"
    ATR = "atr"


@dataclass(frozen=True, slots=True)
class TrailingStopConfig:
    """Declarative trailing-stop settings for one run or strategy."""

    method: TrailingMethod
    percent: float | None = None
    points: float | None = None
    atr_multiplier: float | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.enabled:
            return
        if self.method is TrailingMethod.PERCENT:
            if self.percent is None or self.percent <= 0:
                raise ValueError("percent trailing requires a positive percent")
        elif self.method is TrailingMethod.POINTS:
            if self.points is None or self.points <= 0:
                raise ValueError("points trailing requires a positive points distance")
        elif self.method is TrailingMethod.ATR:
            if self.atr_multiplier is None or self.atr_multiplier <= 0:
                raise ValueError("atr trailing requires a positive atr multiplier")
        else:
            raise ValueError(f"unknown trailing method: {self.method}")


@dataclass(slots=True)
class TrailingStopManager:
    """Mutable trailing-stop state for one open position."""

    config: TrailingStopConfig
    side: PositionSide
    entry_price: float
    atr_at_entry: float | None = None
    highest_price_since_entry: float = 0.0
    lowest_price_since_entry: float = 0.0
    current_trailing_stop: float | None = None
    initial_trailing_stop: float | None = None
    current_stop_reason: str = "TRAILING_STOP"

    @classmethod
    def open(
        cls,
        *,
        config: TrailingStopConfig,
        side: PositionSide,
        entry_price: float,
        atr_at_entry: float | None,
    ) -> TrailingStopManager:
        manager = cls(
            config=config,
            side=side,
            entry_price=entry_price,
            atr_at_entry=atr_at_entry,
            highest_price_since_entry=entry_price,
            lowest_price_since_entry=entry_price,
        )
        manager.current_trailing_stop = manager._candidate_stop(atr=atr_at_entry)
        manager.initial_trailing_stop = manager.current_trailing_stop
        return manager

    def on_bar(self, bar: Bar, atr: float | None) -> None:
        """Update extremes and ratchet the trailing stop using this bar's range."""
        if self.side is PositionSide.LONG:
            self.highest_price_since_entry = max(self.highest_price_since_entry, bar.high)
        else:
            self.lowest_price_since_entry = min(self.lowest_price_since_entry, bar.low)

        candidate = self._candidate_stop(atr=atr)
        if candidate is None:
            return
        if self.current_trailing_stop is None:
            self.current_trailing_stop = candidate
            return
        if self.side is PositionSide.LONG:
            self.current_trailing_stop = max(self.current_trailing_stop, candidate)
        else:
            self.current_trailing_stop = min(self.current_trailing_stop, candidate)

    def is_breached(self, bar: Bar) -> bool:
        """Return whether this bar's range touched the trailing stop."""
        if self.current_trailing_stop is None:
            return False
        if self.side is PositionSide.LONG:
            return bar.low <= self.current_trailing_stop
        return bar.high >= self.current_trailing_stop

    def observe_excursions(self, bar: Bar, *, quantity: float) -> tuple[float, float]:
        """Return running max favourable and adverse excursion in currency."""
        if self.side is PositionSide.LONG:
            favourable = max(0.0, (bar.high - self.entry_price) * quantity)
            adverse = max(0.0, (self.entry_price - bar.low) * quantity)
        else:
            favourable = max(0.0, (self.entry_price - bar.low) * quantity)
            adverse = max(0.0, (bar.high - self.entry_price) * quantity)
        return favourable, adverse

    def _candidate_stop(self, *, atr: float | None) -> float | None:
        if not self.config.enabled:
            return None
        if self.side is PositionSide.LONG:
            reference = self.highest_price_since_entry
            distance = self._distance(atr=atr)
            if distance is None:
                return None
            return reference - distance
        reference = self.lowest_price_since_entry
        distance = self._distance(atr=atr)
        if distance is None:
            return None
        return reference + distance

    def _distance(self, *, atr: float | None) -> float | None:
        if self.config.method is TrailingMethod.PERCENT:
            assert self.config.percent is not None
            reference = (
                self.highest_price_since_entry
                if self.side is PositionSide.LONG
                else self.lowest_price_since_entry
            )
            return reference * (self.config.percent / 100.0)
        if self.config.method is TrailingMethod.POINTS:
            assert self.config.points is not None
            return self.config.points
        assert self.config.atr_multiplier is not None
        effective_atr = atr if atr is not None and atr > 0 else self.atr_at_entry
        if effective_atr is None or effective_atr <= 0:
            return None
        return effective_atr * self.config.atr_multiplier
