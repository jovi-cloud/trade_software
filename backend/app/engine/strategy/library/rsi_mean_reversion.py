"""RSI mean reversion: buy oversold, sell the recovery."""

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
from app.engine.indicators.momentum import RelativeStrengthIndex
from app.engine.indicators.trend import SimpleMovingAverage
from app.engine.strategy.framework import EntrySignal, ExitSignal, MarketView, StrategyBase
from app.engine.strategy.library._shared import (
    GROUP_FILTERS,
    GROUP_SIGNAL,
    capital_pct_param,
    direction_param,
    fractional_param,
    less_than,
    max_bars_param,
    percent_risk,
    percent_stop_params,
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

FILTER_OFF = 0


class RsiMeanReversionStrategy(StrategyBase):
    """Long when RSI is oversold, short when overbought, exit on the return to neutral."""

    metadata = StrategyMetadata(
        id="rsi_mean_reversion",
        name="RSI Mean Reversion",
        description=(
            "Buys oversold RSI readings and sells overbought ones, exiting when RSI "
            "returns to a neutral band."
        ),
        version="1.0.0",
        author="Platform",
        category=StrategyCategory.MEAN_REVERSION,
        markets=(MarketType.EQUITY, MarketType.INDEX, MarketType.FX, MarketType.CRYPTO),
        timeframes=(Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4, Timeframe.D1),
        tags=("mean-reversion", "rsi", "oscillator", "counter-trend"),
        risk_level=RiskLevel.MEDIUM,
        supports_long=True,
        supports_short=True,
        supports_intraday=True,
        supports_swing=True,
        supports_position_trading=False,
        documentation=StrategyDocumentation(
            overview=(
                "Counter-trend by construction: it assumes an extreme RSI reading "
                "reflects short-term exhaustion that price will partially retrace. The "
                "optional trend filter exists because this assumption fails hardest "
                "when fighting a strong trend - an RSI of 20 in a genuine downtrend is "
                "not a bargain, it is a warning."
            ),
            indicators=(
                "RSI over `rsi_period` closes",
                "Optional trend SMA over `trend_filter_period` closes",
            ),
            entry_rules=(
                "Long when RSI crosses down through `oversold_level`",
                "Short when RSI crosses up through `overbought_level`",
                "With the trend filter enabled, longs require close above the SMA and "
                "shorts require close below it",
            ),
            exit_rules=(
                "Close a long when RSI recovers to `exit_level` or above",
                "Close a short when RSI falls to `100 - exit_level` or below",
                "Percent stop, target and the bar limit can exit sooner",
            ),
            risk_rules=(
                "A time limit is on by default: a reversion trade that has not worked "
                "within a few dozen bars was probably not a reversion",
            ),
            known_limitations=(
                "Loses badly in trending markets - the entry condition fires "
                "repeatedly on the way down and each one is early.",
                "RSI needs `rsi_period + 1` bars to be defined, and Wilder smoothing "
                "means early values still carry seeding influence.",
                "Symmetric thresholds assume symmetric behaviour; equity indices are "
                "not symmetric, and the short side historically performs worse.",
            ),
        ),
        examples=(
            StrategyExample(
                title="Classic 14 / 30 / 70",
                description="Textbook levels, both directions, on daily bars.",
                instrument="NIFTY",
                timeframe=Timeframe.D1,
                params={"rsi_period": 14, "oversold_level": 30.0, "overbought_level": 70.0},
            ),
            StrategyExample(
                title="Aggressive 2-period, long only with trend filter",
                description=(
                    "A short RSI with deep thresholds and a 200-bar trend filter - the "
                    "buy-the-dip-in-an-uptrend configuration."
                ),
                instrument="RELIANCE",
                timeframe=Timeframe.D1,
                params={
                    "rsi_period": 2,
                    "oversold_level": 10.0,
                    "exit_level": 60.0,
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
                    "Optional trend filter and a default time-based exit.",
                ),
            ),
        ),
    )

    parameters = (
        period_param(
            "rsi_period",
            description="RSI lookback.",
            default=14,
            minimum=2,
            maximum=100,
            order=10,
        ),
        ParamSpec(
            name="oversold_level",
            type=ParamType.FLOAT,
            description="RSI level below which a long is taken.",
            default=30.0,
            minimum=1.0,
            maximum=49.0,
            step=1.0,
            group=GROUP_SIGNAL,
            display_order=20,
            rules=less_than("overbought_level"),
        ),
        ParamSpec(
            name="overbought_level",
            type=ParamType.FLOAT,
            description="RSI level above which a short is taken.",
            default=70.0,
            minimum=51.0,
            maximum=99.0,
            step=1.0,
            group=GROUP_SIGNAL,
            display_order=30,
        ),
        ParamSpec(
            name="exit_level",
            type=ParamType.FLOAT,
            description=(
                "RSI level a long exits at. Shorts use the mirror level (100 minus this)."
            ),
            default=55.0,
            minimum=40.0,
            maximum=80.0,
            step=1.0,
            group=GROUP_SIGNAL,
            display_order=40,
            tooltip="Closer to 50 exits sooner with a smaller average win.",
        ),
        ParamSpec(
            name="trend_filter_period",
            type=ParamType.INTEGER,
            description="SMA that requires trade direction to agree with trend. 0 disables it.",
            default=0,
            minimum=0,
            maximum=500,
            step=1,
            group=GROUP_FILTERS,
            display_order=10,
        ),
        direction_param(),
        capital_pct_param(),
        *percent_stop_params(stop_default=3.0, target_default=0.0),
        max_bars_param(default=20),
        fractional_param(),
        *trailing_stop_params(),
    )

    def declare_indicators(self) -> Mapping[str, Indicator]:
        indicators: dict[str, Indicator] = {
            "rsi": RelativeStrengthIndex(self.params.integer("rsi_period"))
        }
        trend_period = self.params.integer("trend_filter_period")
        if trend_period > FILTER_OFF:
            indicators["trend_sma"] = SimpleMovingAverage(trend_period)
        return indicators

    def declare_risk(self) -> RiskRules:
        return percent_risk(self.params)

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        oversold = self.params.number("oversold_level")
        overbought = self.params.number("overbought_level")
        rsi = view.value("rsi")

        # Crossing *into* the zone rather than merely being in it: otherwise a
        # long oversold stretch re-fires the same signal on every bar.
        entered_oversold = self.check(
            "RSI Crossed Into Oversold",
            passed=view.crossed_level_below("rsi", oversold),
            actual="warming up" if rsi is None else f"{rsi:.2f}",
            expected=f"crossing down through {oversold:g}",
        )
        entered_overbought = self.check(
            "RSI Crossed Into Overbought",
            passed=view.crossed_level_above("rsi", overbought),
            actual="warming up" if rsi is None else f"{rsi:.2f}",
            expected=f"crossing up through {overbought:g}",
        )
        trend_up, trend_down = self._trend_gate(view)

        if entered_oversold and trend_up:
            return EntrySignal(PositionSide.LONG, f"RSI crossed below {oversold:g}")
        if entered_overbought and trend_down:
            return EntrySignal(PositionSide.SHORT, f"RSI crossed above {overbought:g}")
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        position = view.position
        rsi = view.value("rsi")
        if position is None or rsi is None:
            return None
        is_long = getattr(position, "side", "") == PositionSide.LONG.value
        long_exit_level = self.params.number("exit_level")
        short_exit_level = 100.0 - long_exit_level

        recovered = self.check(
            "RSI Returned To Neutral",
            passed=(rsi >= long_exit_level) if is_long else (rsi <= short_exit_level),
            actual=f"{rsi:.2f}",
            expected=(
                f"at or above {long_exit_level:g}"
                if is_long
                else f"at or below {short_exit_level:g}"
            ),
        )
        return ExitSignal("RSI returned to the neutral band") if recovered else None

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
