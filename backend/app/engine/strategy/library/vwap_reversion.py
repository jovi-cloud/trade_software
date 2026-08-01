"""VWAP reversion - an intraday strategy, and the reference for session handling.

Read this one if your strategy needs to know what time it is at the exchange.
Bars carry UTC milliseconds; ``session_timezone`` converts them, the session VWAP
re-anchors at each local session open, and the risk rules flatten the position
before the close rather than carrying it overnight.
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
from app.engine.indicators.volume import SessionVwap
from app.engine.strategy.framework import EntrySignal, ExitSignal, MarketView, StrategyBase
from app.engine.strategy.library._shared import (
    GROUP_SIGNAL,
    capital_pct_param,
    direction_param,
    fractional_param,
    max_bars_param,
    percent_risk,
    percent_stop_params,
    session_timezone_param,
    time_param,
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


class VwapReversionStrategy(StrategyBase):
    """Fade price stretched away from session VWAP, target the return to it."""

    metadata = StrategyMetadata(
        id="vwap_reversion",
        name="VWAP Reversion",
        description=(
            "Intraday mean reversion to the session VWAP: enters when price is "
            "stretched a set percentage away from it and exits on the return."
        ),
        version="1.0.0",
        author="Platform",
        category=StrategyCategory.MEAN_REVERSION,
        markets=(MarketType.EQUITY, MarketType.INDEX, MarketType.FUTURES),
        timeframes=(Timeframe.M1, Timeframe.M3, Timeframe.M5, Timeframe.M15, Timeframe.M30),
        tags=("mean-reversion", "vwap", "intraday", "volume"),
        risk_level=RiskLevel.HIGH,
        supports_long=True,
        supports_short=True,
        supports_intraday=True,
        supports_swing=False,
        supports_position_trading=False,
        documentation=StrategyDocumentation(
            overview=(
                "Session VWAP is the day's volume-weighted reference price and a level "
                "a great deal of intraday flow is measured against. This strategy "
                "assumes price stretched well away from it during a session tends to "
                "be pulled back. It is strictly intraday: the position is flattened "
                "before the session close, and no entry is taken late in the day when "
                "there is not enough session left for the reversion to happen."
            ),
            indicators=(
                "Session VWAP, re-anchored at each exchange-local session start",
                "Signed distance of the close from VWAP, in percent",
            ),
            entry_rules=(
                "Long when the close is at least `entry_distance_pct` below VWAP",
                "Short when the close is at least `entry_distance_pct` above VWAP",
                "No entries at or after `no_entry_after` exchange time",
            ),
            exit_rules=(
                "Close when price comes back within `exit_distance_pct` of VWAP",
                "Flatten unconditionally at `exit_at_time` exchange time",
                "Percent stop and the bar limit can exit sooner",
            ),
            risk_rules=(
                "Hard session exit so no position is ever carried overnight",
                "Entry window closes before the session end",
            ),
            known_limitations=(
                "Needs real volume. On a dataset with zero or synthetic volume the VWAP "
                "degrades to an unweighted typical-price average and the strategy is "
                "measuring something else.",
                "A trending session runs price away from VWAP all day; this strategy "
                "will fight it repeatedly. The stop is the only defence and it is "
                "essential here.",
                "Session boundaries are derived from local calendar dates, so an "
                "instrument whose session spans midnight in the chosen timezone will "
                "be split incorrectly.",
                "Exits fill at the next bar's open, not at the VWAP touch itself.",
            ),
        ),
        examples=(
            StrategyExample(
                title="NSE 5-minute fade",
                description=(
                    "0.5% stretch from VWAP on Indian equity hours, flat by 15:15 "
                    "with no new entries after 14:45."
                ),
                instrument="RELIANCE",
                timeframe=Timeframe.M5,
                params={
                    "session_timezone": "Asia/Kolkata",
                    "entry_distance_pct": 0.5,
                    "exit_distance_pct": 0.1,
                    "no_entry_after": "14:45",
                    "exit_at_time": "15:15",
                },
            ),
            StrategyExample(
                title="US equity 15-minute fade, long only",
                description="Buy-the-dip-to-VWAP on US hours, flat by 15:50 Eastern.",
                instrument="SPY",
                timeframe=Timeframe.M15,
                params={
                    "session_timezone": "America/New_York",
                    "entry_distance_pct": 0.4,
                    "no_entry_after": "15:00",
                    "exit_at_time": "15:50",
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
                    "Session-anchored VWAP with hard session exit and entry cutoff.",
                ),
            ),
        ),
    )

    parameters = (
        ParamSpec(
            name="entry_distance_pct",
            type=ParamType.PERCENTAGE,
            description="How far the close must be from VWAP before a trade is taken.",
            default=0.5,
            minimum=0.05,
            maximum=10.0,
            step=0.05,
            group=GROUP_SIGNAL,
            display_order=10,
            tooltip="Scale this to the instrument's typical intraday range.",
        ),
        ParamSpec(
            name="exit_distance_pct",
            type=ParamType.PERCENTAGE,
            description="How close to VWAP price must return before the trade is closed.",
            default=0.1,
            minimum=0.0,
            maximum=5.0,
            step=0.05,
            group=GROUP_SIGNAL,
            display_order=20,
            tooltip="0 requires price to touch VWAP exactly, which rarely happens.",
        ),
        session_timezone_param(default="Asia/Kolkata"),
        time_param(
            "no_entry_after",
            description="Exchange-local time after which no new position is opened.",
            default="14:45",
            order=20,
            tooltip="Leave enough session for the reversion to play out.",
        ),
        time_param(
            "exit_at_time",
            description="Exchange-local time at which any open position is flattened.",
            default="15:15",
            order=30,
        ),
        direction_param(),
        capital_pct_param(),
        *percent_stop_params(stop_default=1.0, target_default=0.0),
        max_bars_param(default=60),
        fractional_param(),
        *trailing_stop_params(),
    )

    def declare_indicators(self) -> Mapping[str, Indicator]:
        return {"vwap": SessionVwap(self.session_timezone)}

    def declare_risk(self) -> RiskRules:
        return percent_risk(
            self.params,
            exit_at_time=self.params.text("exit_at_time"),
            no_entry_after=self.params.text("no_entry_after"),
        )

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        distance = view.value("vwap", "distance_pct")
        threshold = self.params.number("entry_distance_pct")

        stretched_below = self.check(
            "Price Stretched Below VWAP",
            passed=distance is not None and distance <= -threshold,
            actual="warming up" if distance is None else f"{distance:+.3f}% from VWAP",
            expected=f"at or below -{threshold:g}%",
        )
        stretched_above = self.check(
            "Price Stretched Above VWAP",
            passed=distance is not None and distance >= threshold,
            actual="warming up" if distance is None else f"{distance:+.3f}% from VWAP",
            expected=f"at or above +{threshold:g}%",
        )
        has_volume = self.check(
            "Session Has Volume",
            passed=(view.value("vwap", "session_volume") or 0.0) > 0,
            actual=f"{view.value('vwap', 'session_volume') or 0.0:g}",
            expected="greater than zero",
        )

        if stretched_below and has_volume:
            return EntrySignal(PositionSide.LONG, f"Price {threshold:g}% or more below VWAP")
        if stretched_above and has_volume:
            return EntrySignal(PositionSide.SHORT, f"Price {threshold:g}% or more above VWAP")
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        position = view.position
        distance = view.value("vwap", "distance_pct")
        if position is None or distance is None:
            return None
        is_long = getattr(position, "side", "") == PositionSide.LONG.value
        threshold = self.params.number("exit_distance_pct")

        # A long was opened below VWAP, so "reverted" means the gap has closed
        # to within the exit band from below - or price has overshot above it.
        reverted = self.check(
            "Price Reverted Toward VWAP",
            passed=(distance >= -threshold) if is_long else (distance <= threshold),
            actual=f"{distance:+.3f}% from VWAP",
            expected=(
                f"at or above -{threshold:g}%" if is_long else f"at or below +{threshold:g}%"
            ),
        )
        return ExitSignal("Price reverted to the VWAP band") if reverted else None
