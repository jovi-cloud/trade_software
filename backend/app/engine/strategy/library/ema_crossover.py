"""EMA Crossover - the canonical trend-following reference strategy.

Read this one first if you are writing a strategy: it exercises every part of
the framework surface and nothing else. Indicators are declared, conditions are
traced through ``self.check``, entry and exit rules return signals, and risk is
declared rather than computed. There is no order code, no cash arithmetic and no
engine import anywhere in the file.
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
from app.engine.indicators.trend import ExponentialMovingAverage, SimpleMovingAverage
from app.engine.strategy.framework import (
    EntrySignal,
    ExitSignal,
    MarketView,
    StrategyBase,
)
from app.engine.strategy.library._shared import (
    GROUP_FILTERS,
    atr_risk,
    atr_stop_params,
    capital_pct_param,
    direction_param,
    fractional_param,
    less_than,
    max_bars_param,
    period_param,
    trailing_stop_params,
)
from app.engine.strategy.metadata import (
    ChangelogEntry,
    StrategyDocumentation,
    StrategyExample,
    StrategyMetadata,
)
from app.engine.strategy.params import ParamSpec
from app.engine.strategy.risk import RiskRules

#: A trend filter period of zero means "no filter", which keeps the long SMA out
#: of the warmup calculation instead of costing 200 bars of data for nothing.
FILTER_OFF = 0


class EmaCrossoverStrategy(StrategyBase):
    """Long when the fast EMA crosses above the slow EMA, short on the reverse."""

    metadata = StrategyMetadata(
        id="ema_crossover",
        name="EMA Crossover",
        description=(
            "Trades the crossover of a fast and a slow exponential moving average, "
            "optionally filtered by a long-term trend average."
        ),
        version="1.0.0",
        author="Platform",
        category=StrategyCategory.TREND_FOLLOWING,
        markets=(
            MarketType.EQUITY,
            MarketType.INDEX,
            MarketType.FUTURES,
            MarketType.CRYPTO,
            MarketType.FX,
        ),
        timeframes=(
            Timeframe.M15,
            Timeframe.M30,
            Timeframe.H1,
            Timeframe.H4,
            Timeframe.D1,
        ),
        tags=("trend", "moving-average", "crossover", "beginner"),
        risk_level=RiskLevel.MEDIUM,
        supports_long=True,
        supports_short=True,
        supports_intraday=True,
        supports_swing=True,
        supports_position_trading=True,
        documentation=StrategyDocumentation(
            overview=(
                "The oldest trend-following idea there is: when a short average of "
                "price rises through a longer one, recent prices are above the "
                "established level and the trend is assumed to have turned up. The "
                "edge, where it exists, is in capturing the middle of sustained moves "
                "and accepting many small losses in ranges."
            ),
            indicators=(
                "Fast EMA over `fast_period` closes",
                "Slow EMA over `slow_period` closes",
                "Optional trend SMA over `trend_filter_period` closes",
            ),
            entry_rules=(
                "Long when the fast EMA crosses from at-or-below to above the slow EMA",
                "Short when the fast EMA crosses from at-or-above to below the slow EMA",
                "When the trend filter is enabled, longs also require close above the "
                "trend SMA and shorts require close below it",
            ),
            exit_rules=(
                "Close a long when the fast EMA crosses back below the slow EMA",
                "Close a short when the fast EMA crosses back above the slow EMA",
                "Protective risk rules can exit earlier",
            ),
            known_limitations=(
                "Whipsaws badly in range-bound markets: crossovers cluster and each "
                "one costs commission and slippage.",
                "Signals are late by construction - a moving average is a lag.",
                "Both EMAs are seeded from the first `period` bars of the dataset, so "
                "the first signals in a short dataset carry less history than later ones.",
            ),
            references=("Kaufman, Trading Systems and Methods, chapter on trend calculations",),
        ),
        examples=(
            StrategyExample(
                title="Classic 12/26 on daily bars",
                description=(
                    "The MACD periods used as a plain crossover, long-only, with a "
                    "200-day trend filter."
                ),
                instrument="NIFTY",
                timeframe=Timeframe.D1,
                params={
                    "fast_period": 12,
                    "slow_period": 26,
                    "trend_filter_period": 200,
                    "direction": "long_only",
                },
            ),
            StrategyExample(
                title="Fast 9/21 on hourly bars",
                description="A shorter pair for intraday swing trades, both directions.",
                instrument="BANKNIFTY",
                timeframe=Timeframe.H1,
                params={
                    "fast_period": 9,
                    "slow_period": 21,
                    "trend_filter_period": 0,
                    "stop_atr_multiple": 1.5,
                },
            ),
        ),
        changelog=(
            ChangelogEntry(
                version="1.0.0",
                date="2026-07-30",
                changes=(
                    "First release on the Strategy Framework.",
                    "ATR-scaled stop, R-multiple target and optional trend filter.",
                ),
            ),
        ),
    )

    parameters = (
        period_param(
            "fast_period",
            description="Lookback for the fast EMA.",
            default=12,
            minimum=2,
            maximum=200,
            order=10,
            rules=less_than("slow_period"),
            tooltip="Must be shorter than the slow period, or there is no crossover to trade.",
        ),
        period_param(
            "slow_period",
            description="Lookback for the slow EMA.",
            default=26,
            minimum=3,
            maximum=400,
            order=20,
        ),
        ParamSpec(
            name="trend_filter_period",
            type=ParamType.INTEGER,
            description="Long-term SMA that gates entries by trend direction. 0 disables it.",
            default=200,
            minimum=0,
            maximum=500,
            step=1,
            group=GROUP_FILTERS,
            display_order=10,
            tooltip="Costs this many extra warmup bars when enabled.",
        ),
        direction_param(),
        capital_pct_param(),
        *atr_stop_params(),
        max_bars_param(),
        fractional_param(),
        *trailing_stop_params(),
    )

    def declare_indicators(self) -> Mapping[str, Indicator]:
        indicators: dict[str, Indicator] = {
            "ema_fast": ExponentialMovingAverage(self.params.integer("fast_period")),
            "ema_slow": ExponentialMovingAverage(self.params.integer("slow_period")),
        }
        trend_period = self.params.integer("trend_filter_period")
        if trend_period > FILTER_OFF:
            indicators["trend_sma"] = SimpleMovingAverage(trend_period)
        return indicators

    def declare_risk(self) -> RiskRules:
        return atr_risk(self.params)

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        # Every condition is evaluated into a local before being combined:
        # `a and b` would short-circuit and leave `b` untraced, and an untraced
        # condition is exactly the one you need when a signal did not fire.
        crossed_up = self.check(
            "Fast EMA Crossed Above Slow EMA",
            passed=view.crossed_above("ema_fast", "ema_slow"),
            actual=self._spread(view),
            expected="fast above slow after being at or below",
        )
        crossed_down = self.check(
            "Fast EMA Crossed Below Slow EMA",
            passed=view.crossed_below("ema_fast", "ema_slow"),
            actual=self._spread(view),
            expected="fast below slow after being at or above",
        )
        trend_up, trend_down = self._trend_gate(view)

        if crossed_up and trend_up:
            return EntrySignal(PositionSide.LONG, "Fast EMA crossed above slow EMA")
        if crossed_down and trend_down:
            return EntrySignal(PositionSide.SHORT, "Fast EMA crossed below slow EMA")
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        position = view.position
        if position is None:
            return None
        is_long = getattr(position, "side", "") == PositionSide.LONG.value

        reversed_long = self.check(
            "Crossover Reversed Against Long",
            passed=is_long and view.crossed_below("ema_fast", "ema_slow"),
            actual=self._spread(view),
            expected="fast back below slow while long",
        )
        reversed_short = self.check(
            "Crossover Reversed Against Short",
            passed=not is_long and view.crossed_above("ema_fast", "ema_slow"),
            actual=self._spread(view),
            expected="fast back above slow while short",
        )
        if reversed_long or reversed_short:
            return ExitSignal("Crossover reversed against the open position")
        return None

    def _trend_gate(self, view: MarketView) -> tuple[bool, bool]:
        """Trend filter verdicts for long and short. Both pass when disabled."""
        if self.params.integer("trend_filter_period") == FILTER_OFF:
            return True, True
        trend = view.value("trend_sma")
        close = view.bar.close
        above = self.check(
            "Close Above Trend Filter",
            passed=trend is not None and close > trend,
            actual=f"close {close:g} vs trend {trend:g}"
            if trend is not None
            else "trend warming up",
            expected="close above the trend SMA",
        )
        below = self.check(
            "Close Below Trend Filter",
            passed=trend is not None and close < trend,
            actual=f"close {close:g} vs trend {trend:g}"
            if trend is not None
            else "trend warming up",
            expected="close below the trend SMA",
        )
        return above, below

    def _spread(self, view: MarketView) -> str:
        fast, slow = view.value("ema_fast"), view.value("ema_slow")
        if fast is None or slow is None:
            return "warming up"
        return f"fast {fast:.4f} vs slow {slow:.4f}"
