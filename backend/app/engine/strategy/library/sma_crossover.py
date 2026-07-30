"""SMA Crossover with a minimum-separation filter.

The plain crossover's failure mode is well known: when the two averages sit on
top of each other, price noise flips the signal every few bars and commission
grinds the account down. This variant requires the averages to be a configurable
distance apart before it will act, which is the cheapest available defence.
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
from app.engine.indicators.trend import SimpleMovingAverage
from app.engine.strategy.framework import EntrySignal, ExitSignal, MarketView, StrategyBase
from app.engine.strategy.library._shared import (
    GROUP_FILTERS,
    capital_pct_param,
    direction_param,
    fractional_param,
    less_than,
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


class SmaCrossoverStrategy(StrategyBase):
    """Long when the fast SMA is above the slow SMA by a minimum margin."""

    metadata = StrategyMetadata(
        id="sma_crossover",
        name="SMA Crossover",
        description=(
            "Simple moving average crossover that ignores signals until the two "
            "averages are separated by a minimum percentage."
        ),
        version="1.0.0",
        author="Platform",
        category=StrategyCategory.TREND_FOLLOWING,
        markets=(MarketType.EQUITY, MarketType.INDEX, MarketType.FUTURES, MarketType.CRYPTO),
        timeframes=(Timeframe.M30, Timeframe.H1, Timeframe.H4, Timeframe.D1, Timeframe.W1),
        tags=("trend", "moving-average", "crossover", "beginner"),
        risk_level=RiskLevel.MEDIUM,
        supports_long=True,
        supports_short=True,
        supports_intraday=False,
        supports_swing=True,
        supports_position_trading=True,
        documentation=StrategyDocumentation(
            overview=(
                "Two simple moving averages, and one addition that matters: the "
                "crossover is only acted on once the averages are at least "
                "`min_separation_pct` apart. Near-flat markets produce crossovers "
                "with almost no separation, and those are the ones that lose money."
            ),
            indicators=(
                "Fast SMA over `fast_period` closes",
                "Slow SMA over `slow_period` closes",
            ),
            entry_rules=(
                "Long when the fast SMA is above the slow SMA and was not on the "
                "previous bar, and their separation is at least `min_separation_pct`",
                "Short on the mirror-image condition",
            ),
            exit_rules=(
                "Close when the averages cross back the other way",
                "Percent stop, percent target and optional trailing stop can exit sooner",
            ),
            risk_rules=("Percent-of-entry stop and target, sized as a share of capital",),
            known_limitations=(
                "The separation filter delays entry, which trades fewer bad signals "
                "for a worse entry price on the good ones.",
                "Simple averages weight a 200-bar-old close as heavily as yesterday's; "
                "use the EMA variant if that bothers you.",
                "Not intended for intraday timeframes - the separation filter needs "
                "moves larger than typical intraday noise to be meaningful.",
            ),
        ),
        examples=(
            StrategyExample(
                title="Golden cross, long only",
                description="The 50/200 daily cross that generalist commentary talks about.",
                instrument="NIFTY",
                timeframe=Timeframe.D1,
                params={
                    "fast_period": 50,
                    "slow_period": 200,
                    "min_separation_pct": 0.5,
                    "direction": "long_only",
                    "stop_loss_pct": 5.0,
                    "take_profit_pct": 0.0,
                },
            ),
        ),
        changelog=(
            ChangelogEntry(
                version="1.0.0",
                date="2026-07-30",
                changes=(
                    "First release on the Strategy Framework.",
                    "Minimum-separation filter to suppress flat-market whipsaw.",
                ),
            ),
        ),
    )

    parameters = (
        period_param(
            "fast_period",
            description="Lookback for the fast SMA.",
            default=50,
            minimum=2,
            maximum=300,
            order=10,
            rules=less_than("slow_period"),
        ),
        period_param(
            "slow_period",
            description="Lookback for the slow SMA.",
            default=200,
            minimum=3,
            maximum=500,
            order=20,
        ),
        ParamSpec(
            name="min_separation_pct",
            type=ParamType.PERCENTAGE,
            description=(
                "Minimum gap between the averages, as a percent of the slow average, "
                "before a crossover is acted on. 0 accepts every crossover."
            ),
            default=0.5,
            minimum=0.0,
            maximum=10.0,
            step=0.1,
            group=GROUP_FILTERS,
            display_order=10,
            tooltip="Raise this in choppy markets; lower it if you are missing real trends.",
        ),
        direction_param(),
        capital_pct_param(),
        *percent_stop_params(stop_default=5.0, target_default=0.0),
        max_bars_param(),
        fractional_param(),
    )

    def declare_indicators(self) -> Mapping[str, Indicator]:
        return {
            "sma_fast": SimpleMovingAverage(self.params.integer("fast_period")),
            "sma_slow": SimpleMovingAverage(self.params.integer("slow_period")),
        }

    def declare_risk(self) -> RiskRules:
        return percent_risk(self.params)

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        crossed_up = self.check(
            "Fast SMA Crossed Above Slow SMA",
            passed=view.crossed_above("sma_fast", "sma_slow"),
            actual=self._state(view),
            expected="fast above slow after being at or below",
        )
        crossed_down = self.check(
            "Fast SMA Crossed Below Slow SMA",
            passed=view.crossed_below("sma_fast", "sma_slow"),
            actual=self._state(view),
            expected="fast below slow after being at or above",
        )
        separated = self.check(
            "Averages Sufficiently Separated",
            passed=self._separation_pct(view) >= self.params.number("min_separation_pct"),
            actual=f"{self._separation_pct(view):.3f}%",
            expected=f"at least {self.params.number('min_separation_pct'):g}%",
        )

        if crossed_up and separated:
            return EntrySignal(PositionSide.LONG, "Fast SMA crossed above slow SMA with margin")
        if crossed_down and separated:
            return EntrySignal(PositionSide.SHORT, "Fast SMA crossed below slow SMA with margin")
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        position = view.position
        if position is None:
            return None
        is_long = getattr(position, "side", "") == PositionSide.LONG.value
        fast, slow = view.value("sma_fast"), view.value("sma_slow")
        if fast is None or slow is None:
            return None

        against = self.check(
            "Averages Crossed Against Position",
            passed=(fast < slow) if is_long else (fast > slow),
            actual=self._state(view),
            expected="fast on the wrong side of slow for this position",
        )
        return ExitSignal("Moving averages crossed against the position") if against else None

    def _separation_pct(self, view: MarketView) -> float:
        fast, slow = view.value("sma_fast"), view.value("sma_slow")
        if fast is None or slow is None or slow == 0:
            return 0.0
        return abs(fast - slow) / abs(slow) * 100.0

    def _state(self, view: MarketView) -> str:
        fast, slow = view.value("sma_fast"), view.value("sma_slow")
        if fast is None or slow is None:
            return "warming up"
        return f"fast {fast:.4f} vs slow {slow:.4f}"
