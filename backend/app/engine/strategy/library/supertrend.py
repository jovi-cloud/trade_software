"""SuperTrend direction-flip following.

The SuperTrend line is itself a trailing stop, so this strategy deliberately
leans on the indicator for its exit rather than layering a second stop on top -
that is the whole design of the indicator and duplicating it just widens the
effective stop.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.enums import (
    MarketType,
    ParamType,
    PositionSide,
    RiskLevel,
    StrategyCategory,
    Timeframe,
)
from app.engine.indicators.base import Indicator
from app.engine.indicators.trend import SimpleMovingAverage, SuperTrend
from app.engine.strategy.framework import EntrySignal, ExitSignal, MarketView, StrategyBase
from app.engine.strategy.library._shared import (
    GROUP_FILTERS,
    GROUP_SIGNAL,
    capital_pct_param,
    direction_param,
    fractional_param,
    max_bars_param,
    percent_risk,
    percent_stop_params,
    period_param,
)
from app.engine.strategy.metadata import (
    ChangelogEntry,
    StrategyDocumentation,
    StrategyExample,
    StrategyMetadata,
)
from app.engine.strategy.params import ParamSpec
from app.engine.strategy.risk import RiskRules

FILTER_OFF = 0
UPTREND = 1.0


class SuperTrendStrategy(StrategyBase):
    """Enter on a SuperTrend direction flip, exit on the opposite flip."""

    metadata = StrategyMetadata(
        id="supertrend",
        name="SuperTrend",
        description=(
            "Follows the SuperTrend line: enters when the ATR-banded trend direction "
            "flips and exits when it flips back."
        ),
        version="1.0.0",
        author="Platform",
        category=StrategyCategory.TREND_FOLLOWING,
        markets=(MarketType.EQUITY, MarketType.INDEX, MarketType.FUTURES, MarketType.CRYPTO),
        timeframes=(Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4, Timeframe.D1),
        tags=("trend", "atr", "supertrend", "trailing-stop"),
        risk_level=RiskLevel.MEDIUM,
        supports_long=True,
        supports_short=True,
        supports_intraday=True,
        supports_swing=True,
        supports_position_trading=True,
        documentation=StrategyDocumentation(
            overview=(
                "SuperTrend places a band at a multiple of ATR from the midpoint of "
                "each bar and lets that band ratchet only in the direction of the "
                "trend. Price closing through the band flips the direction. Because "
                "the band scales with ATR, the same multiplier behaves consistently "
                "across quiet and volatile regimes - which is the property a fixed "
                "percentage stop lacks."
            ),
            indicators=(
                "SuperTrend over `atr_period` with `atr_multiplier`",
                "Optional trend SMA over `trend_filter_period` closes",
            ),
            entry_rules=(
                "Long when SuperTrend direction flips from down to up",
                "Short when it flips from up to down",
                "With the trend filter enabled, the close must also agree with the long-term SMA",
            ),
            exit_rules=(
                "Close when the SuperTrend direction flips against the position - the "
                "line acts as the trailing stop",
                "The percent stop and target are available but off by default",
            ),
            risk_rules=("The SuperTrend line is the primary exit; explicit stops default to off",),
            known_limitations=(
                "Always in the market when the filter is off: every exit is also an "
                "entry in the other direction, so range-bound periods produce "
                "back-to-back losers.",
                "A larger `atr_multiplier` means fewer flips and a wider effective "
                "stop; the two cannot be tuned independently.",
                "The published SuperTrend recursion carries state from the first bar "
                "onwards, so results depend slightly on where the dataset starts.",
            ),
        ),
        examples=(
            StrategyExample(
                title="Standard 10 / 3.0",
                description="The most commonly published configuration, both directions.",
                instrument="NIFTY",
                timeframe=Timeframe.D1,
                params={"atr_period": 10, "atr_multiplier": 3.0},
            ),
            StrategyExample(
                title="Long-only with trend filter",
                description="Only takes upward flips that agree with a 200-bar SMA.",
                instrument="RELIANCE",
                timeframe=Timeframe.H1,
                params={
                    "atr_period": 14,
                    "atr_multiplier": 2.5,
                    "trend_filter_period": 200,
                    "direction": "long_only",
                },
            ),
        ),
        changelog=(
            ChangelogEntry(
                version="1.0.0",
                date="2026-07-30",
                changes=(
                    "First release on the Strategy Framework.",
                    "Direction-flip entries and exits with an optional SMA regime filter.",
                ),
            ),
        ),
    )

    parameters = (
        period_param(
            "atr_period",
            description="ATR lookback used to size the SuperTrend bands.",
            default=10,
            minimum=2,
            maximum=100,
            order=10,
        ),
        ParamSpec(
            name="atr_multiplier",
            type=ParamType.FLOAT,
            description="Band distance from the bar midpoint, in ATRs.",
            default=3.0,
            minimum=0.5,
            maximum=10.0,
            step=0.1,
            group=GROUP_SIGNAL,
            display_order=20,
            tooltip="Higher means fewer flips and a wider effective trailing stop.",
        ),
        ParamSpec(
            name="trend_filter_period",
            type=ParamType.INTEGER,
            description="SMA that gates entries by longer-term direction. 0 disables it.",
            default=0,
            minimum=0,
            maximum=500,
            step=1,
            group=GROUP_FILTERS,
            display_order=10,
        ),
        direction_param(),
        capital_pct_param(),
        *percent_stop_params(stop_default=0.0, target_default=0.0),
        max_bars_param(),
        fractional_param(),
    )

    def declare_indicators(self) -> Mapping[str, Indicator]:
        indicators: dict[str, Indicator] = {
            "supertrend": SuperTrend(
                self.params.integer("atr_period"),
                self.params.number("atr_multiplier"),
            )
        }
        trend_period = self.params.integer("trend_filter_period")
        if trend_period > FILTER_OFF:
            indicators["trend_sma"] = SimpleMovingAverage(trend_period)
        return indicators

    def declare_risk(self) -> RiskRules:
        return percent_risk(self.params)

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        flipped_up = self.check(
            "SuperTrend Flipped To Uptrend",
            passed=self._flipped(view, to=UPTREND),
            actual=self._state(view),
            expected="direction changed from -1 to +1",
        )
        flipped_down = self.check(
            "SuperTrend Flipped To Downtrend",
            passed=self._flipped(view, to=-UPTREND),
            actual=self._state(view),
            expected="direction changed from +1 to -1",
        )
        trend_up, trend_down = self._trend_gate(view)

        if flipped_up and trend_up:
            return EntrySignal(PositionSide.LONG, "SuperTrend flipped to uptrend")
        if flipped_down and trend_down:
            return EntrySignal(PositionSide.SHORT, "SuperTrend flipped to downtrend")
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        position = view.position
        if position is None:
            return None
        is_long = getattr(position, "side", "") == PositionSide.LONG.value
        direction = view.value("supertrend", "direction")

        against = self.check(
            "SuperTrend Turned Against Position",
            passed=direction is not None and ((direction < 0) if is_long else (direction > 0)),
            actual=self._state(view),
            expected="direction opposing the open position",
        )
        return ExitSignal("SuperTrend direction turned against the position") if against else None

    def _flipped(self, view: MarketView, *, to: float) -> bool:
        now = view.value("supertrend", "direction")
        was = view.previous("supertrend", "direction")
        if now is None or was is None:
            return False
        return now == to and was != to

    def _trend_gate(self, view: MarketView) -> tuple[bool, bool]:
        if self.params.integer("trend_filter_period") == FILTER_OFF:
            return True, True
        trend = view.value("trend_sma")
        close = view.bar.close
        above = self.check(
            "Close Above Trend Filter",
            passed=trend is not None and close > trend,
            actual="warming up" if trend is None else f"close {close:g} vs SMA {trend:g}",
            expected="close above the trend SMA",
        )
        below = self.check(
            "Close Below Trend Filter",
            passed=trend is not None and close < trend,
            actual="warming up" if trend is None else f"close {close:g} vs SMA {trend:g}",
            expected="close below the trend SMA",
        )
        return above, below

    def _state(self, view: MarketView) -> str:
        direction = view.value("supertrend", "direction")
        line = view.value("supertrend")
        if direction is None or line is None:
            return "warming up"
        label = "uptrend" if direction > 0 else "downtrend"
        return f"{label} (line {line:.4f})"
