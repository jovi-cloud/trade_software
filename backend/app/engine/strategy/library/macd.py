"""MACD signal-line crossover with an optional zero-line regime filter."""

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
from app.engine.indicators.trend import Macd
from app.engine.strategy.framework import EntrySignal, ExitSignal, MarketView, StrategyBase
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


class MacdStrategy(StrategyBase):
    """Long when the MACD line crosses above its signal line, short on the reverse."""

    metadata = StrategyMetadata(
        id="macd",
        name="MACD",
        description=(
            "Trades MACD line / signal line crossovers, optionally requiring the MACD "
            "line to be on the correct side of zero."
        ),
        version="1.0.0",
        author="Platform",
        category=StrategyCategory.MOMENTUM,
        markets=(MarketType.EQUITY, MarketType.INDEX, MarketType.FUTURES, MarketType.CRYPTO),
        timeframes=(Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4, Timeframe.D1),
        tags=("momentum", "macd", "crossover", "oscillator"),
        risk_level=RiskLevel.MEDIUM,
        supports_long=True,
        supports_short=True,
        supports_intraday=True,
        supports_swing=True,
        supports_position_trading=False,
        documentation=StrategyDocumentation(
            overview=(
                "MACD measures the distance between a fast and a slow EMA, and its "
                "signal line smooths that distance. A crossover therefore says the "
                "rate of trend change has itself turned - earlier than a price "
                "crossover, at the cost of more false positives. The zero-line filter "
                "trades some of those false positives back for lateness."
            ),
            indicators=(
                "MACD line: EMA(`fast_period`) minus EMA(`slow_period`)",
                "Signal line: EMA(`signal_period`) of the MACD line",
                "Histogram: MACD line minus signal line",
            ),
            entry_rules=(
                "Long when the MACD line crosses above the signal line",
                "Short when the MACD line crosses below the signal line",
                "With `require_zero_line_agreement` on, longs also need MACD above "
                "zero and shorts need it below",
            ),
            exit_rules=(
                "Close when the MACD line crosses back through the signal line",
                "ATR stop, R-multiple target and optional ATR trail can exit sooner",
            ),
            known_limitations=(
                "MACD is unbounded and not comparable across instruments or across "
                "price levels of the same instrument - a threshold tuned on one is "
                "meaningless on another.",
                "Signal-line crossovers are frequent; commission and slippage matter "
                "more here than for slower trend systems.",
                "The signal EMA is seeded from the first valid MACD values, so warmup "
                "is `slow_period + signal_period - 1` bars.",
            ),
        ),
        examples=(
            StrategyExample(
                title="Standard 12/26/9",
                description="The textbook configuration, both directions, on daily bars.",
                instrument="NIFTY",
                timeframe=Timeframe.D1,
                params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
            ),
            StrategyExample(
                title="Zero-line confirmed",
                description=(
                    "Same periods, but only trades crossovers that agree with the "
                    "sign of the MACD line."
                ),
                instrument="BANKNIFTY",
                timeframe=Timeframe.H1,
                params={"require_zero_line_agreement": True, "stop_atr_multiple": 2.5},
            ),
        ),
        changelog=(
            ChangelogEntry(
                version="1.0.0",
                date="2026-07-30",
                changes=(
                    "First release on the Strategy Framework.",
                    "Optional zero-line agreement filter.",
                ),
            ),
        ),
    )

    parameters = (
        period_param(
            "fast_period",
            description="Fast EMA lookback inside MACD.",
            default=12,
            minimum=2,
            maximum=100,
            order=10,
            rules=less_than("slow_period"),
        ),
        period_param(
            "slow_period",
            description="Slow EMA lookback inside MACD.",
            default=26,
            minimum=3,
            maximum=200,
            order=20,
        ),
        period_param(
            "signal_period",
            description="EMA lookback applied to the MACD line.",
            default=9,
            minimum=2,
            maximum=100,
            order=30,
        ),
        ParamSpec(
            name="require_zero_line_agreement",
            type=ParamType.BOOLEAN,
            description=(
                "Only take crossovers where the MACD line is already on the side "
                "matching the trade direction."
            ),
            default=False,
            group=GROUP_FILTERS,
            display_order=10,
            tooltip="Fewer, later, historically cleaner signals.",
        ),
        direction_param(),
        capital_pct_param(),
        *atr_stop_params(stop_default=2.5, target_default=2.0),
        max_bars_param(),
        fractional_param(),
        *trailing_stop_params(),
    )

    def declare_indicators(self) -> Mapping[str, Indicator]:
        return {
            "macd": Macd(
                self.params.integer("fast_period"),
                self.params.integer("slow_period"),
                self.params.integer("signal_period"),
            )
        }

    def declare_risk(self) -> RiskRules:
        return atr_risk(self.params)

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        crossed_up = self.check(
            "MACD Crossed Above Signal",
            passed=view.crossed_above("macd.line", "macd.signal"),
            actual=self._state(view),
            expected="MACD line above signal after being at or below",
        )
        crossed_down = self.check(
            "MACD Crossed Below Signal",
            passed=view.crossed_below("macd.line", "macd.signal"),
            actual=self._state(view),
            expected="MACD line below signal after being at or above",
        )
        zero_up, zero_down = self._zero_line_gate(view)

        if crossed_up and zero_up:
            return EntrySignal(PositionSide.LONG, "MACD crossed above its signal line")
        if crossed_down and zero_down:
            return EntrySignal(PositionSide.SHORT, "MACD crossed below its signal line")
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        position = view.position
        if position is None:
            return None
        is_long = getattr(position, "side", "") == PositionSide.LONG.value

        against = self.check(
            "MACD Crossed Against Position",
            passed=(
                view.crossed_below("macd.line", "macd.signal")
                if is_long
                else view.crossed_above("macd.line", "macd.signal")
            ),
            actual=self._state(view),
            expected="MACD crossing back through the signal line",
        )
        return ExitSignal("MACD crossed back through its signal line") if against else None

    def _zero_line_gate(self, view: MarketView) -> tuple[bool, bool]:
        if not self.params.flag("require_zero_line_agreement"):
            return True, True
        line = view.value("macd.line")
        above = self.check(
            "MACD Above Zero",
            passed=line is not None and line > 0,
            actual="warming up" if line is None else f"{line:.4f}",
            expected="greater than 0",
        )
        below = self.check(
            "MACD Below Zero",
            passed=line is not None and line < 0,
            actual="warming up" if line is None else f"{line:.4f}",
            expected="less than 0",
        )
        return above, below

    def _state(self, view: MarketView) -> str:
        line, signal = view.value("macd.line"), view.value("macd.signal")
        if line is None or signal is None:
            return "warming up"
        return f"line {line:.4f} vs signal {signal:.4f}"
