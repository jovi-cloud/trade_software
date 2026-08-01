"""Declarative risk rules: position sizing and protective exits.

## Why this lives in the framework and not in strategies

Part 1 of the framework brief says a strategy contains indicators, conditions,
entry rules, exit rules and risk rules - and never cash or portfolio
arithmetic. Position sizing is arithmetic over capital, so a strategy *declares*
``PercentOfEquity(10.0)`` and this module does the division. The same applies to
stop and target levels: the strategy declares "two ATRs below entry" and the
subtraction happens here.

## Why protective exits are bar-close decisions, not resting orders

The execution engine supports market orders only, filled at the next bar's open
(ARCHITECTURE.md 2.2). There is no resting stop order to place, so a stop here
means: *at the close of a bar whose range touched the stop level, submit a
market close*, which fills at the next open. That is a strictly more
conservative model than assuming a fill at the stop price - it never credits a
fill the data cannot prove - but it does mean realised stop losses are wider
than the declared level in fast markets. This is a documented limitation of the
framework, not of the execution mathematics, which are untouched.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Literal

from app.domain.enums import PositionSide
from app.engine.bars import Bar
from app.engine.execution.trailing_stop import (
    TrailingMethod,
    TrailingStopConfig,
    TrailingStopManager,
)
from app.engine.indicators.session import SessionClock

#: Quantities below this are treated as "cannot afford a position" rather than
#: submitted and rejected by the order service for being non-positive.
MIN_QUANTITY = 1e-9


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------


class SizingRule(ABC):
    """Turns available capital into an order quantity."""

    @abstractmethod
    def quantity(self, *, capital: float, price: float, stop_distance: float | None) -> float:
        """Raw (unrounded) quantity. Return 0 when the rule cannot be applied."""

    @abstractmethod
    def describe(self) -> str:
        """One line for the generated documentation and condition traces."""


@dataclass(frozen=True, slots=True)
class FixedQuantity(SizingRule):
    """Always trade the same number of units. The simplest reproducible baseline."""

    quantity_per_trade: float = 1.0

    def quantity(self, *, capital: float, price: float, stop_distance: float | None) -> float:
        return self.quantity_per_trade

    def describe(self) -> str:
        return f"Fixed size of {_number(self.quantity_per_trade)} unit(s) per trade"


@dataclass(frozen=True, slots=True)
class FixedNotional(SizingRule):
    """Deploy a fixed cash amount per trade, regardless of account size."""

    amount: float

    def quantity(self, *, capital: float, price: float, stop_distance: float | None) -> float:
        if price <= 0:
            return 0.0
        return min(self.amount, capital) / price

    def describe(self) -> str:
        return f"Fixed notional of {_number(self.amount)} per trade"


@dataclass(frozen=True, slots=True)
class PercentOfEquity(SizingRule):
    """Deploy ``percent`` of available capital (2.5 means 2.5%)."""

    percent: float

    def quantity(self, *, capital: float, price: float, stop_distance: float | None) -> float:
        if price <= 0 or capital <= 0:
            return 0.0
        return capital * (self.percent / 100.0) / price

    def describe(self) -> str:
        return f"{_number(self.percent)}% of available capital per trade"


@dataclass(frozen=True, slots=True)
class RiskPerTrade(SizingRule):
    """Size so that hitting the stop costs ``percent`` of capital.

    Requires a stop rule: without a stop distance there is no defined risk to
    divide by, so the rule reports zero rather than guessing a size.
    """

    percent: float

    def quantity(self, *, capital: float, price: float, stop_distance: float | None) -> float:
        if stop_distance is None or stop_distance <= 0 or capital <= 0:
            return 0.0
        risk_budget = capital * (self.percent / 100.0)
        raw = risk_budget / stop_distance
        # Never lever up beyond the cash on hand: this platform models an
        # unlevered cash account, so a tight stop must not imply a position
        # larger than the account can pay for.
        affordable = capital / price if price > 0 else 0.0
        return min(raw, affordable)

    def describe(self) -> str:
        return f"Sized so a stop-out risks {_number(self.percent)}% of capital"


# ---------------------------------------------------------------------------
# Protective levels
# ---------------------------------------------------------------------------


class LevelRule(ABC):
    """Computes a price level from the entry, in the direction the rule implies."""

    @abstractmethod
    def distance(self, *, entry_price: float, atr: float | None) -> float | None:
        """Absolute price distance from the reference price, or None if unavailable."""

    @abstractmethod
    def describe(self) -> str: ...


@dataclass(frozen=True, slots=True)
class PercentDistance(LevelRule):
    """A distance expressed as a percentage of the entry price."""

    percent: float

    def distance(self, *, entry_price: float, atr: float | None) -> float | None:
        if entry_price <= 0:
            return None
        return entry_price * (self.percent / 100.0)

    def describe(self) -> str:
        return f"{_number(self.percent)}% of entry price"


@dataclass(frozen=True, slots=True)
class AtrDistance(LevelRule):
    """A distance expressed as a multiple of ATR.

    For stops and targets the ATR is sampled **at entry** and frozen for the
    life of the trade; a stop that re-derives its level from the current ATR
    would drift on every bar, which is a trailing stop, not a stop.
    """

    multiple: float

    def distance(self, *, entry_price: float, atr: float | None) -> float | None:
        if atr is None or atr <= 0:
            return None
        return atr * self.multiple

    def describe(self) -> str:
        return f"{_number(self.multiple)}x ATR"


@dataclass(frozen=True, slots=True)
class RMultipleDistance(LevelRule):
    """A target expressed as a multiple of the stop distance (an R multiple).

    Resolved by ``RiskRules`` rather than here, because it needs the stop
    distance the stop rule produced.
    """

    multiple: float

    def distance(self, *, entry_price: float, atr: float | None) -> float | None:
        return None

    def describe(self) -> str:
        return f"{_number(self.multiple)}R (multiple of the stop distance)"


# ---------------------------------------------------------------------------
# The rule set
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QuantityResolution:
    """A position size together with the arithmetic that produced it."""

    #: Size the sizing rule asked for, before the lot-rounding policy.
    raw: float
    #: Size actually submitted, after flooring or 6dp rounding.
    quantity: float
    #: Stop distance the sizing rule was given, where it needed one.
    stop_distance: float | None
    #: Whether fractional sizes were permitted for this run.
    fractional: bool

    @property
    def floored_to_zero(self) -> bool:
        """A tradeable size was requested and the rounding policy erased it."""
        return self.quantity <= 0.0 < self.raw


@dataclass(frozen=True, slots=True)
class RiskRules:
    """Everything a strategy declares about sizing and protective exits.

    Every field is optional: a strategy that declares nothing gets one unit per
    trade and no protective exits, which is the behaviour of a hand-written
    strategy that only calls ``ctx.buy()``.
    """

    sizing: SizingRule = field(default_factory=FixedQuantity)
    stop_loss: LevelRule | None = None
    take_profit: LevelRule | None = None
    trailing_stop: LevelRule | None = None
    #: Force an exit after this many bars in the trade.
    max_bars_in_trade: int | None = None
    #: Exchange-local ``HH:MM`` after which any open position is flattened.
    exit_at_time: str | None = None
    #: Block entries at or after this exchange-local ``HH:MM``.
    no_entry_after: str | None = None
    #: ATR period used by ATR-based sizing and level rules.
    atr_period: int = 14
    #: Allow non-integer quantities (crypto and FX; false for equities/futures).
    fractional_quantity: bool = False
    #: Preferred trailing-stop configuration. When set, takes precedence over
    #: the legacy ``trailing_stop`` level rule.
    trailing_config: TrailingStopConfig | None = None

    @property
    def needs_atr(self) -> bool:
        trailing_needs_atr = (
            self.trailing_config is not None
            and self.trailing_config.enabled
            and self.trailing_config.method is TrailingMethod.ATR
        )
        return trailing_needs_atr or any(
            isinstance(rule, AtrDistance)
            for rule in (self.stop_loss, self.take_profit, self.trailing_stop)
        )

    @property
    def needs_session_clock(self) -> bool:
        return self.exit_at_time is not None or self.no_entry_after is not None

    def stop_distance(self, *, entry_price: float, atr: float | None) -> float | None:
        if self.stop_loss is None:
            return None
        return self.stop_loss.distance(entry_price=entry_price, atr=atr)

    def target_distance(self, *, entry_price: float, atr: float | None) -> float | None:
        if self.take_profit is None:
            return None
        if isinstance(self.take_profit, RMultipleDistance):
            stop = self.stop_distance(entry_price=entry_price, atr=atr)
            if stop is None:
                return None
            return stop * self.take_profit.multiple
        return self.take_profit.distance(entry_price=entry_price, atr=atr)

    def resolve_quantity(self, *, capital: float, price: float, atr: float | None) -> float:
        """Apply the sizing rule and the lot-rounding policy. Never negative."""
        return self.resolve_quantity_detail(capital=capital, price=price, atr=atr).quantity

    def resolve_quantity_detail(
        self, *, capital: float, price: float, atr: float | None
    ) -> QuantityResolution:
        """Size a position and keep the arithmetic that produced it.

        The intermediate values are what make a zero size explainable. A run that
        deploys 20% of 1,000 on a 995-rupee share sizes 0.201 shares and floors
        that to nothing; reporting only the final ``0`` leaves no way to tell
        that apart from "no signal fired" or "the stop rule had no distance".
        """
        stop_distance = self.stop_distance(entry_price=price, atr=atr)
        raw = self.sizing.quantity(
            capital=capital,
            price=price,
            stop_distance=stop_distance,
        )
        if not math.isfinite(raw) or raw <= 0:
            return QuantityResolution(
                raw=raw if math.isfinite(raw) else 0.0,
                quantity=0.0,
                stop_distance=stop_distance,
                fractional=self.fractional_quantity,
            )
        # Six decimals matches the engine's quantity rounding policy.
        quantity = round(raw, 6) if self.fractional_quantity else float(math.floor(raw))
        return QuantityResolution(
            raw=raw,
            quantity=quantity,
            stop_distance=stop_distance,
            fractional=self.fractional_quantity,
        )

    def describe(self) -> tuple[str, ...]:
        """Human-readable rule list for the generated documentation."""
        lines = [self.sizing.describe()]
        if self.stop_loss is not None:
            lines.append(f"Stop loss at {self.stop_loss.describe()} from entry")
        if self.take_profit is not None:
            lines.append(f"Take profit at {self.take_profit.describe()} from entry")
        if self.trailing_stop is not None:
            lines.append(
                f"Trailing stop at {self.trailing_stop.describe()} from the best price reached"
            )
        if self.trailing_config is not None and self.trailing_config.enabled:
            lines.append(_describe_trailing_config(self.trailing_config))
        if self.max_bars_in_trade is not None:
            lines.append(f"Force an exit after {self.max_bars_in_trade} bars in the trade")
        if self.exit_at_time is not None:
            lines.append(f"Flatten any open position at {self.exit_at_time} exchange time")
        if self.no_entry_after is not None:
            lines.append(f"No new entries at or after {self.no_entry_after} exchange time")
        if not self.fractional_quantity:
            lines.append("Quantities are whole units (fractional sizes are floored)")
        return tuple(lines)


@dataclass(frozen=True, slots=True)
class StopLossOverride:
    """Run-level replacement for a strategy's declared stop-loss rule."""

    mode: Literal["percent", "atr", "disabled"]
    percent: float | None = None
    atr_multiple: float | None = None

    def __post_init__(self) -> None:
        if self.mode == "percent":
            if self.percent is None or self.percent <= 0:
                raise ValueError("percent stop override requires a positive percent")
        elif self.mode == "atr":
            if self.atr_multiple is None or self.atr_multiple <= 0:
                raise ValueError("atr stop override requires a positive atr_multiple")
        elif self.mode != "disabled":
            raise ValueError(f"unknown stop loss override mode: {self.mode}")


def apply_stop_loss_override(rules: RiskRules, override: StopLossOverride) -> RiskRules:
    """Replace only the stop-loss rule; sizing, targets and session exits are kept."""
    if override.mode == "disabled":
        return replace(rules, stop_loss=None)
    if override.mode == "percent":
        assert override.percent is not None
        return replace(rules, stop_loss=PercentDistance(override.percent))
    assert override.atr_multiple is not None
    return replace(rules, stop_loss=AtrDistance(override.atr_multiple))


# ---------------------------------------------------------------------------
# Per-trade evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RiskExit:
    """A protective exit the framework decided to take."""

    #: Stable machine-readable reason, surfaced in condition traces.
    code: str
    #: Sentence shown in the Trade Inspector.
    description: str
    #: The level that was breached, where the rule has one.
    level: float | None = None


@dataclass(slots=True)
class TradeRiskState:
    """Mutable per-trade risk state. Created when a position appears."""

    side: PositionSide
    entry_price: float
    entry_bar_index: int
    atr_at_entry: float | None
    best_price: float
    stop_level: float | None = None
    target_level: float | None = None
    trailing: TrailingStopManager | None = None
    highest_price_since_entry: float = 0.0
    lowest_price_since_entry: float = 0.0
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    max_profit: float = 0.0
    max_drawdown_in_trade: float = 0.0
    trade_seq: int = 0

    @classmethod
    def open(
        cls,
        *,
        side: PositionSide,
        entry_price: float,
        entry_bar_index: int,
        atr: float | None,
        rules: RiskRules,
        quantity: float = 1.0,
        trade_seq: int = 0,
    ) -> TradeRiskState:
        state = cls(
            side=side,
            entry_price=entry_price,
            entry_bar_index=entry_bar_index,
            atr_at_entry=atr,
            best_price=entry_price,
            highest_price_since_entry=entry_price,
            lowest_price_since_entry=entry_price,
            trade_seq=trade_seq,
        )
        stop = rules.stop_distance(entry_price=entry_price, atr=atr)
        target = rules.target_distance(entry_price=entry_price, atr=atr)
        sign = 1.0 if side is PositionSide.LONG else -1.0
        if stop is not None:
            state.stop_level = entry_price - sign * stop
        if target is not None:
            state.target_level = entry_price + sign * target
        trailing_config = resolve_trailing_config(rules)
        if trailing_config is not None:
            state.trailing = TrailingStopManager.open(
                config=trailing_config,
                side=side,
                entry_price=entry_price,
                atr_at_entry=atr,
            )
        state._update_excursions(bar=None, quantity=quantity, mark_price=entry_price)
        return state

    def observe(self, bar: Bar, *, quantity: float = 1.0, atr: float | None = None) -> None:
        """Update extremes, trailing stop, and excursion statistics for one bar."""
        if self.side is PositionSide.LONG:
            self.best_price = max(self.best_price, bar.high)
            self.highest_price_since_entry = max(self.highest_price_since_entry, bar.high)
        else:
            self.best_price = min(self.best_price, bar.low)
            self.lowest_price_since_entry = min(self.lowest_price_since_entry, bar.low)
        if self.trailing is not None:
            self.trailing.on_bar(bar, atr if atr is not None else self.atr_at_entry)
        self._update_excursions(bar=bar, quantity=quantity, mark_price=bar.close)

    def trailing_level(self, rules: RiskRules, atr: float | None) -> float | None:
        if self.trailing is not None:
            return self.trailing.current_trailing_stop
        if rules.trailing_stop is None:
            return None
        distance = rules.trailing_stop.distance(entry_price=self.best_price, atr=atr)
        if distance is None:
            return None
        sign = 1.0 if self.side is PositionSide.LONG else -1.0
        return self.best_price - sign * distance

    def _update_excursions(
        self, *, bar: Bar | None, quantity: float, mark_price: float
    ) -> None:
        if self.side is PositionSide.LONG:
            favourable = max(0.0, (self.highest_price_since_entry - self.entry_price) * quantity)
            adverse = max(0.0, (self.entry_price - self.lowest_price_since_entry) * quantity)
            floating = (mark_price - self.entry_price) * quantity
        else:
            favourable = max(0.0, (self.entry_price - self.lowest_price_since_entry) * quantity)
            adverse = max(0.0, (self.highest_price_since_entry - self.entry_price) * quantity)
            floating = (self.entry_price - mark_price) * quantity
        self.max_favorable_excursion = max(self.max_favorable_excursion, favourable)
        self.max_adverse_excursion = max(self.max_adverse_excursion, adverse)
        self.max_profit = max(self.max_profit, floating)
        self.max_drawdown_in_trade = max(self.max_drawdown_in_trade, -floating)


def evaluate_risk_exit(
    state: TradeRiskState,
    *,
    bar: Bar,
    bars_held: int,
    rules: RiskRules,
    atr: float | None,
    clock: SessionClock | None,
) -> RiskExit | None:
    """Decide whether a protective rule fires on this bar.

    Precedence is deliberately pessimistic: when a bar's range spans both the
    stop and the target, the stop wins. Bar data cannot tell us which level was
    touched first, and assuming the profitable one is how a backtest flatters
    itself.
    """
    is_long = state.side is PositionSide.LONG

    if state.stop_level is not None and _breached(
        bar, state.stop_level, adverse=True, is_long=is_long
    ):
        return RiskExit(
            code="stop_loss",
            description=(
                f"Stop loss breached: bar {'low' if is_long else 'high'} "
                f"{_number(bar.low if is_long else bar.high)} crossed "
                f"{_number(state.stop_level)}"
            ),
            level=state.stop_level,
        )

    trailing = state.trailing_level(rules, atr)
    if state.trailing is not None:
        if state.trailing.is_breached(bar):
            level = state.trailing.current_trailing_stop
            return RiskExit(
                code="trailing_stop",
                description=(
                    f"Trailing stop breached: best price {_number(state.best_price)} "
                    f"pulled the stop to {_number(level if level is not None else 0.0)}"
                ),
                level=level,
            )
    elif trailing is not None and _breached(bar, trailing, adverse=True, is_long=is_long):
        return RiskExit(
            code="trailing_stop",
            description=(
                f"Trailing stop breached: best price {_number(state.best_price)} "
                f"pulled the stop to {_number(trailing)}"
            ),
            level=trailing,
        )

    if state.target_level is not None and _breached(
        bar, state.target_level, adverse=False, is_long=is_long
    ):
        return RiskExit(
            code="take_profit",
            description=(
                f"Target reached: bar {'high' if is_long else 'low'} "
                f"{_number(bar.high if is_long else bar.low)} crossed "
                f"{_number(state.target_level)}"
            ),
            level=state.target_level,
        )

    if rules.max_bars_in_trade is not None and bars_held >= rules.max_bars_in_trade:
        return RiskExit(
            code="max_bars",
            description=f"Held for {bars_held} bars, the declared maximum",
        )

    if (
        rules.exit_at_time is not None
        and clock is not None
        and clock.is_at_or_after(rules.exit_at_time)
    ):
        return RiskExit(
            code="session_exit",
            description=(
                f"Session exit: local time {clock.local_time:%H:%M} reached {rules.exit_at_time}"
            ),
        )

    return None


def _breached(bar: Bar, level: float, *, adverse: bool, is_long: bool) -> bool:
    """Did this bar's range reach ``level`` in the relevant direction?"""
    if is_long:
        return bar.low <= level if adverse else bar.high >= level
    return bar.high >= level if adverse else bar.low <= level


def _number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def resolve_trailing_config(rules: RiskRules) -> TrailingStopConfig | None:
    """Build trailing configuration from explicit or legacy risk declarations."""
    if rules.trailing_config is not None:
        return rules.trailing_config if rules.trailing_config.enabled else None
    trailing = rules.trailing_stop
    if trailing is None:
        return None
    if isinstance(trailing, PercentDistance):
        return TrailingStopConfig(method=TrailingMethod.PERCENT, percent=trailing.percent)
    if isinstance(trailing, AtrDistance):
        return TrailingStopConfig(method=TrailingMethod.ATR, atr_multiplier=trailing.multiple)
    return None


def _describe_trailing_config(config: TrailingStopConfig) -> str:
    if config.method is TrailingMethod.PERCENT:
        return f"Trailing stop {_number(config.percent or 0.0)}% from the best price reached"
    if config.method is TrailingMethod.POINTS:
        return f"Trailing stop {_number(config.points or 0.0)} points from the best price reached"
    return f"Trailing stop {_number(config.atr_multiplier or 0.0)}x ATR from the best price reached"
