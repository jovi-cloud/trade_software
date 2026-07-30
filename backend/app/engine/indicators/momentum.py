"""Momentum indicators: RSI, rate of change."""

from __future__ import annotations

from app.engine.bars import Bar
from app.engine.indicators.base import Indicator, RollingWindow


class RelativeStrengthIndex(Indicator):
    """Wilder's RSI over ``period`` closes.

    ``RSI = 100 - 100 / (1 + avg_gain / avg_loss)`` where the averages use
    Wilder's smoothing, seeded with the arithmetic mean of the first ``period``
    gains and losses. A window with no losses gives 100 and one with no gains
    gives 0, which is the conventional treatment of the otherwise undefined
    ratio.
    """

    def __init__(self, period: int) -> None:
        super().__init__()
        self._period = period
        self._gain_seed = RollingWindow(period)
        self._loss_seed = RollingWindow(period)
        self._avg_gain: float | None = None
        self._avg_loss: float | None = None
        self._previous_close: float | None = None

    @property
    def warmup_bars(self) -> int:
        # One bar to establish a previous close, then `period` changes.
        return self._period + 1

    def _compute(self, bar: Bar) -> None:
        previous = self._previous_close
        self._previous_close = bar.close
        if previous is None:
            self._publish("value", None)
            return

        change = bar.close - previous
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        if self._avg_gain is None or self._avg_loss is None:
            self._gain_seed.append(gain)
            self._loss_seed.append(loss)
            self._avg_gain = self._gain_seed.mean()
            self._avg_loss = self._loss_seed.mean()
        else:
            n = self._period
            self._avg_gain = (self._avg_gain * (n - 1) + gain) / n
            self._avg_loss = (self._avg_loss * (n - 1) + loss) / n

        if self._avg_gain is None or self._avg_loss is None:
            self._publish("value", None)
            return
        self._publish("value", _rsi_from_averages(self._avg_gain, self._avg_loss))


class RateOfChange(Indicator):
    """Percent change over ``period`` bars, expressed as 2.5 for 2.5%.

    Matches the project-wide percent convention (ARCHITECTURE.md 8): percent
    values are stored and displayed as 12.5, never 0.125.
    """

    def __init__(self, period: int) -> None:
        super().__init__()
        self._period = period
        # period + 1 closes are needed to span `period` intervals.
        self._window = RollingWindow(period + 1)

    @property
    def warmup_bars(self) -> int:
        return self._period + 1

    def _compute(self, bar: Bar) -> None:
        self._window.append(bar.close)
        if not self._window.is_full:
            self._publish("value", None)
            return
        past = self._window.first
        if past == 0:
            self._publish("value", 0.0)
            return
        self._publish("value", (self._window.last - past) / past * 100.0)


def _rsi_from_averages(average_gain: float, average_loss: float) -> float:
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    if average_gain == 0:
        return 0.0
    return 100.0 - 100.0 / (1.0 + average_gain / average_loss)
