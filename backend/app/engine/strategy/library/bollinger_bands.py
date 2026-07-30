"""Bollinger Bands, in both of the ways people actually trade them.

Reversion and breakout are opposite trades on the same indicator, and which one
works depends entirely on the instrument's regime. Shipping them as one strategy
with a ``mode`` parameter rather than two near-identical files means a trader can
A/B the two hypotheses on the same data without re-entering every other setting -
and the run history records which mode produced which result.
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
from app.engine.indicators.volatility import BollingerBands
from app.engine.strategy.framework import EntrySignal, ExitSignal, MarketView, StrategyBase
from app.engine.strategy.library._shared import (
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
from app.engine.strategy.params import ParamChoice, ParamSpec
from app.engine.strategy.risk import RiskRules

MODE_REVERSION = "reversion"
MODE_BREAKOUT = "breakout"


class BollingerBandsStrategy(StrategyBase):
    """Trade band touches as reversion, or band breaks as breakout."""

    metadata = StrategyMetadata(
        id="bollinger_bands",
        name="Bollinger Bands",
        description=(
            "Trades Bollinger Band extremes either as mean reversion (fade the touch) "
            "or as breakout (join the break), selected by parameter."
        ),
        version="1.0.0",
        author="Platform",
        category=StrategyCategory.VOLATILITY,
        markets=(MarketType.EQUITY, MarketType.INDEX, MarketType.FX, MarketType.CRYPTO),
        timeframes=(Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4, Timeframe.D1),
        tags=("volatility", "bollinger", "mean-reversion", "breakout"),
        risk_level=RiskLevel.MEDIUM,
        supports_long=True,
        supports_short=True,
        supports_intraday=True,
        supports_swing=True,
        supports_position_trading=False,
        documentation=StrategyDocumentation(
            overview=(
                "Bollinger Bands mark where price is unusual relative to its own recent "
                "distribution. In `reversion` mode the strategy fades a close outside "
                "the band and targets the middle band. In `breakout` mode it does the "
                "opposite, treating the same event as the start of an expansion. Both "
                "are legitimate; they suit different instruments, and running the same "
                "settings in both modes is a fast way to find out which."
            ),
            indicators=(
                "Bollinger Bands over `period` closes at `deviations` standard deviations",
                "Derived %B and bandwidth, published by the indicator",
            ),
            entry_rules=(
                "Reversion mode: long when the close is below the lower band, short "
                "when above the upper band",
                "Breakout mode: long when the close is above the upper band, short "
                "when below the lower band",
                "With `require_squeeze` on, breakout entries also need bandwidth below "
                "`max_bandwidth_pct`, so only breaks out of a compressed range qualify",
            ),
            exit_rules=(
                "Reversion mode: close when price returns to the middle band",
                "Breakout mode: close when price falls back inside the opposite side "
                "of the middle band",
                "Percent stop, target and the bar limit can exit sooner",
            ),
            known_limitations=(
                "Reversion mode has unbounded loss potential on a genuine trend break "
                "unless the stop is left enabled.",
                "Bands widen *after* volatility arrives, so a breakout signal often "
                "coincides with the band already having expanded past the price.",
                "Standard deviation over 20 bars is a poor estimator; band levels move "
                "materially with one outlier bar entering or leaving the window.",
            ),
        ),
        examples=(
            StrategyExample(
                title="Classic 20 / 2.0 reversion",
                description="Fade closes outside the standard bands, target the mean.",
                instrument="NIFTY",
                timeframe=Timeframe.D1,
                params={"period": 20, "deviations": 2.0, "mode": MODE_REVERSION},
            ),
            StrategyExample(
                title="Squeeze breakout",
                description=(
                    "Only takes band breaks that happen out of a compressed range, long-only."
                ),
                instrument="BANKNIFTY",
                timeframe=Timeframe.H1,
                params={
                    "mode": MODE_BREAKOUT,
                    "require_squeeze": True,
                    "max_bandwidth_pct": 4.0,
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
                    "Reversion and breakout modes with an optional squeeze filter.",
                ),
            ),
        ),
    )

    parameters = (
        ParamSpec(
            name="mode",
            type=ParamType.CHOICE,
            description="Whether to fade band extremes or trade breaks through them.",
            default=MODE_REVERSION,
            choices=(
                ParamChoice(
                    MODE_REVERSION,
                    "Mean reversion",
                    "Fade closes outside the bands, target the middle band",
                ),
                ParamChoice(
                    MODE_BREAKOUT,
                    "Breakout",
                    "Join closes outside the bands as the start of an expansion",
                ),
            ),
            group=GROUP_SIGNAL,
            display_order=5,
        ),
        period_param(
            "period",
            description="Lookback for the middle band and the standard deviation.",
            default=20,
            minimum=2,
            maximum=200,
            order=10,
        ),
        ParamSpec(
            name="deviations",
            type=ParamType.FLOAT,
            description="Band distance from the middle band, in standard deviations.",
            default=2.0,
            minimum=0.5,
            maximum=5.0,
            step=0.1,
            group=GROUP_SIGNAL,
            display_order=20,
        ),
        ParamSpec(
            name="require_squeeze",
            type=ParamType.BOOLEAN,
            description="Breakout mode only: require a compressed band before the break.",
            default=False,
            group=GROUP_SIGNAL,
            display_order=30,
        ),
        ParamSpec(
            name="max_bandwidth_pct",
            type=ParamType.PERCENTAGE,
            description=(
                "Squeeze threshold: band width as a percent of the middle band must be "
                "below this for a breakout to qualify."
            ),
            default=4.0,
            minimum=0.1,
            maximum=50.0,
            step=0.1,
            group=GROUP_SIGNAL,
            display_order=40,
            tooltip="Ignored unless require_squeeze is on and mode is breakout.",
        ),
        direction_param(),
        capital_pct_param(),
        *percent_stop_params(stop_default=3.0, target_default=0.0),
        max_bars_param(default=30),
        fractional_param(),
    )

    def declare_indicators(self) -> Mapping[str, Indicator]:
        return {
            "bb": BollingerBands(self.params.integer("period"), self.params.number("deviations"))
        }

    def declare_risk(self) -> RiskRules:
        return percent_risk(self.params)

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        upper = view.value("bb", "upper")
        lower = view.value("bb", "lower")
        close = view.bar.close

        above_upper = self.check(
            "Close Above Upper Band",
            passed=upper is not None and close > upper,
            actual="warming up" if upper is None else f"{close:.4f} vs upper {upper:.4f}",
            expected="close above the upper band",
        )
        below_lower = self.check(
            "Close Below Lower Band",
            passed=lower is not None and close < lower,
            actual="warming up" if lower is None else f"{close:.4f} vs lower {lower:.4f}",
            expected="close below the lower band",
        )
        squeeze_ok = self._squeeze_gate(view)

        if self.params.text("mode") == MODE_REVERSION:
            if below_lower:
                return EntrySignal(PositionSide.LONG, "Close fell below the lower band")
            if above_upper:
                return EntrySignal(PositionSide.SHORT, "Close rose above the upper band")
            return None

        if above_upper and squeeze_ok:
            return EntrySignal(PositionSide.LONG, "Close broke above the upper band")
        if below_lower and squeeze_ok:
            return EntrySignal(PositionSide.SHORT, "Close broke below the lower band")
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        position = view.position
        middle = view.value("bb", "middle")
        if position is None or middle is None:
            return None
        is_long = getattr(position, "side", "") == PositionSide.LONG.value
        close = view.bar.close

        if self.params.text("mode") == MODE_REVERSION:
            reached = self.check(
                "Price Returned To Middle Band",
                passed=(close >= middle) if is_long else (close <= middle),
                actual=f"{close:.4f} vs middle {middle:.4f}",
                expected="close back at the middle band",
            )
            return ExitSignal("Price reverted to the middle band") if reached else None

        failed = self.check(
            "Breakout Failed Back Through Middle Band",
            passed=(close < middle) if is_long else (close > middle),
            actual=f"{close:.4f} vs middle {middle:.4f}",
            expected="close back through the middle band against the position",
        )
        return ExitSignal("Breakout failed back through the middle band") if failed else None

    def _squeeze_gate(self, view: MarketView) -> bool:
        """Bandwidth filter. Always passes outside breakout mode with the filter on."""
        if self.params.text("mode") != MODE_BREAKOUT or not self.params.flag("require_squeeze"):
            return True
        bandwidth = view.value("bb", "bandwidth")
        threshold = self.params.number("max_bandwidth_pct")
        # `bandwidth` is a ratio; the parameter is a percentage, matching the
        # project-wide convention that 4.0 means 4%.
        as_percent = None if bandwidth is None else bandwidth * 100.0
        return self.check(
            "Bands Were Squeezed",
            passed=as_percent is not None and as_percent < threshold,
            actual="warming up" if as_percent is None else f"{as_percent:.3f}%",
            expected=f"below {threshold:g}%",
        )
