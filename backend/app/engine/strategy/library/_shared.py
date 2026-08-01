"""Parameter and risk building blocks shared by the built-in strategies.

Ten strategies all need "how much capital per trade", "where is the stop", "when
do I flatten for the session". Declaring those ten times would guarantee ten
slightly different bounds, tooltips and defaults - and the parameter editor is
generated from those declarations, so the inconsistency would be visible to the
trader. Declaring them once here means every built-in strategy presents the same
risk controls in the same order with the same units.

The underscore prefix keeps this module out of registry discovery.
"""

from __future__ import annotations

from app.domain.enums import ParamType, ValidationRuleKind
from app.engine.indicators.session import SESSION_TIMEZONES
from app.engine.execution.trailing_stop import TrailingMethod, TrailingStopConfig
from app.engine.strategy.framework import (
    DIRECTION_BOTH,
    DIRECTION_LONG_ONLY,
    DIRECTION_PARAM,
    DIRECTION_SHORT_ONLY,
    SESSION_TIMEZONE_PARAM,
)
from app.engine.strategy.params import ParamChoice, ParamSpec, ParamValues, ValidationRule
from app.engine.strategy.risk import (
    AtrDistance,
    LevelRule,
    PercentDistance,
    PercentOfEquity,
    RiskRules,
    RMultipleDistance,
    SizingRule,
)

GROUP_SIGNAL = "Signal"
GROUP_FILTERS = "Filters"
GROUP_RISK = "Risk"
GROUP_SESSION = "Session"

#: Zero means "rule disabled" for every optional risk parameter below. A
#: nullable numeric parameter would need a tri-state widget in the generated
#: editor; zero is unambiguous for a distance and keeps the form a number input.
DISABLED = 0.0


def direction_param(*, order: int = 90, default: str = DIRECTION_BOTH) -> ParamSpec:
    """Restrict which sides a strategy may take, without editing its rules."""
    return ParamSpec(
        name=DIRECTION_PARAM,
        type=ParamType.CHOICE,
        description="Which side(s) this strategy is allowed to trade.",
        default=default,
        choices=(
            ParamChoice(DIRECTION_BOTH, "Long and short", "Take signals in both directions"),
            ParamChoice(DIRECTION_LONG_ONLY, "Long only", "Ignore short signals"),
            ParamChoice(DIRECTION_SHORT_ONLY, "Short only", "Ignore long signals"),
        ),
        group=GROUP_FILTERS,
        display_order=order,
        tooltip="Long-only is the right choice for cash equity accounts.",
    )


def session_timezone_param(*, order: int = 10, default: str = "UTC") -> ParamSpec:
    """Exchange timezone. Bars are UTC; session rules are local (see indicators/session.py)."""
    return ParamSpec(
        name=SESSION_TIMEZONE_PARAM,
        type=ParamType.CHOICE,
        description="Exchange timezone used to locate session boundaries and time-based rules.",
        default=default,
        choices=tuple(ParamChoice(value=name, label=label) for name, label in SESSION_TIMEZONES),
        group=GROUP_SESSION,
        display_order=order,
        tooltip="Bar timestamps are UTC; this converts them to exchange local time.",
    )


def time_param(
    name: str,
    *,
    description: str,
    default: str,
    order: int,
    tooltip: str = "",
    group: str = GROUP_SESSION,
) -> ParamSpec:
    return ParamSpec(
        name=name,
        type=ParamType.TIME,
        description=description,
        default=default,
        group=group,
        display_order=order,
        tooltip=tooltip,
    )


def period_param(
    name: str,
    *,
    description: str,
    default: int,
    minimum: int = 2,
    maximum: int = 500,
    order: int,
    group: str = GROUP_SIGNAL,
    tooltip: str = "",
    rules: tuple[ValidationRule, ...] = (),
) -> ParamSpec:
    return ParamSpec(
        name=name,
        type=ParamType.INTEGER,
        description=description,
        default=default,
        minimum=minimum,
        maximum=maximum,
        step=1,
        group=group,
        display_order=order,
        tooltip=tooltip,
        rules=rules,
    )


def capital_pct_param(*, order: int = 10, default: float = 20.0) -> ParamSpec:
    return ParamSpec(
        name="capital_pct",
        type=ParamType.PERCENTAGE,
        description="Share of available capital deployed per trade.",
        default=default,
        minimum=1.0,
        maximum=100.0,
        step=1.0,
        group=GROUP_RISK,
        display_order=order,
        tooltip=(
            "Quantities are floored to whole units, so a small percentage on an "
            "expensive instrument can round down to no trade."
        ),
    )


def percent_stop_params(
    *,
    stop_default: float = 1.0,
    target_default: float = 2.0,
    trailing_default: float = DISABLED,
    order: int = 20,
) -> tuple[ParamSpec, ...]:
    """Percent-of-entry stop, target and trailing stop. Zero disables each."""
    return (
        ParamSpec(
            name="stop_loss_pct",
            type=ParamType.PERCENTAGE,
            description="Stop distance below (long) or above (short) entry. 0 disables the stop.",
            default=stop_default,
            minimum=0.0,
            maximum=25.0,
            step=0.1,
            group=GROUP_RISK,
            display_order=order,
            tooltip=(
                "The engine has no resting stop order: the exit is submitted at the "
                "close of the bar that touched this level and fills at the next open."
            ),
        ),
        ParamSpec(
            name="take_profit_pct",
            type=ParamType.PERCENTAGE,
            description="Target distance from entry. 0 disables the target.",
            default=target_default,
            minimum=0.0,
            maximum=100.0,
            step=0.1,
            group=GROUP_RISK,
            display_order=order + 1,
        ),
        ParamSpec(
            name="trailing_stop_pct",
            type=ParamType.PERCENTAGE,
            description="Trailing stop distance from the best price reached. 0 disables it.",
            default=trailing_default,
            minimum=0.0,
            maximum=25.0,
            step=0.1,
            group=GROUP_RISK,
            display_order=order + 2,
        ),
    )


def atr_stop_params(
    *,
    period_default: int = 14,
    stop_default: float = 2.0,
    target_default: float = 2.0,
    trailing_default: float = DISABLED,
    order: int = 20,
) -> tuple[ParamSpec, ...]:
    """ATR-scaled stop, R-multiple target and ATR trailing stop. Zero disables each."""
    return (
        period_param(
            "atr_period",
            description="ATR lookback used to scale stops and targets to volatility.",
            default=period_default,
            minimum=2,
            maximum=200,
            order=order,
            group=GROUP_RISK,
        ),
        ParamSpec(
            name="stop_atr_multiple",
            type=ParamType.FLOAT,
            description="Stop distance as a multiple of ATR at entry. 0 disables the stop.",
            default=stop_default,
            minimum=0.0,
            maximum=10.0,
            step=0.1,
            group=GROUP_RISK,
            display_order=order + 1,
            tooltip="ATR is sampled at entry and held fixed for the life of the trade.",
        ),
        ParamSpec(
            name="target_r_multiple",
            type=ParamType.FLOAT,
            description="Target as a multiple of the stop distance (R). 0 disables the target.",
            default=target_default,
            minimum=0.0,
            maximum=20.0,
            step=0.1,
            group=GROUP_RISK,
            display_order=order + 2,
            tooltip="Needs a non-zero stop: R is meaningless without a defined risk.",
        ),
        ParamSpec(
            name="trailing_atr_multiple",
            type=ParamType.FLOAT,
            description="Trailing stop as a multiple of current ATR. 0 disables it.",
            default=trailing_default,
            minimum=0.0,
            maximum=10.0,
            step=0.1,
            group=GROUP_RISK,
            display_order=order + 3,
        ),
    )


def trailing_stop_params(*, order: int = 35) -> tuple[ParamSpec, ...]:
    """Unified trailing-stop controls shared by every built-in strategy."""
    return (
        ParamSpec(
            name="enable_trailing_stop",
            type=ParamType.BOOLEAN,
            description="Enable a ratcheting trailing stop for this strategy.",
            default=False,
            group=GROUP_RISK,
            display_order=order,
            tooltip="When off, legacy trailing_stop_pct / trailing_atr_multiple still apply if set.",
        ),
        ParamSpec(
            name="trailing_method",
            type=ParamType.CHOICE,
            description="How the trailing distance is measured from the best price reached.",
            default=TrailingMethod.PERCENT.value,
            choices=(
                ParamChoice(TrailingMethod.PERCENT.value, "Percent", "Trail by % of best price"),
                ParamChoice(TrailingMethod.POINTS.value, "Points", "Trail by fixed price points"),
                ParamChoice(TrailingMethod.ATR.value, "ATR", "Trail by ATR multiple"),
            ),
            group=GROUP_RISK,
            display_order=order + 1,
        ),
        ParamSpec(
            name="trailing_stop_percent",
            type=ParamType.PERCENTAGE,
            description="Trailing distance as a percent of the best price reached.",
            default=2.0,
            minimum=0.1,
            maximum=25.0,
            step=0.1,
            group=GROUP_RISK,
            display_order=order + 2,
        ),
        ParamSpec(
            name="trailing_stop_points",
            type=ParamType.FLOAT,
            description="Trailing distance in absolute price points from the best price reached.",
            default=1.0,
            minimum=0.01,
            maximum=10_000.0,
            step=0.01,
            group=GROUP_RISK,
            display_order=order + 3,
        ),
        ParamSpec(
            name="trailing_stop_atr_multiplier",
            type=ParamType.FLOAT,
            description="Trailing distance as a multiple of ATR.",
            default=2.0,
            minimum=0.1,
            maximum=10.0,
            step=0.1,
            group=GROUP_RISK,
            display_order=order + 4,
        ),
    )


def max_bars_param(*, default: int = 0, order: int = 40) -> ParamSpec:
    return ParamSpec(
        name="max_bars_in_trade",
        type=ParamType.INTEGER,
        description="Force an exit after this many bars. 0 means no time limit.",
        default=default,
        minimum=0,
        maximum=5000,
        step=1,
        group=GROUP_RISK,
        display_order=order,
    )


def fractional_param(*, order: int = 50) -> ParamSpec:
    return ParamSpec(
        name="fractional_quantity",
        type=ParamType.BOOLEAN,
        description="Allow fractional position sizes (crypto and FX). Off floors to whole units.",
        default=False,
        group=GROUP_RISK,
        display_order=order,
    )


def less_than(other: str) -> tuple[ValidationRule, ...]:
    return (ValidationRule(kind=ValidationRuleKind.LESS_THAN_PARAM, other_param=other),)


def greater_than(other: str) -> tuple[ValidationRule, ...]:
    return (ValidationRule(kind=ValidationRuleKind.GREATER_THAN_PARAM, other_param=other),)


# ---------------------------------------------------------------------------
# Risk assembly
# ---------------------------------------------------------------------------


def percent_risk(
    params: ParamValues,
    *,
    sizing: SizingRule | None = None,
    exit_at_time: str | None = None,
    no_entry_after: str | None = None,
) -> RiskRules:
    """Build ``RiskRules`` from the percent-based parameter set."""
    trailing_config = _trailing_config_from_params(params)
    return RiskRules(
        sizing=sizing or PercentOfEquity(params.number("capital_pct")),
        stop_loss=_percent_or_none(params, "stop_loss_pct"),
        take_profit=_percent_or_none(params, "take_profit_pct"),
        trailing_stop=None if trailing_config else _percent_or_none(params, "trailing_stop_pct"),
        trailing_config=trailing_config,
        max_bars_in_trade=_positive_or_none(params, "max_bars_in_trade"),
        exit_at_time=exit_at_time,
        no_entry_after=no_entry_after,
        fractional_quantity=_flag(params, "fractional_quantity"),
    )


def atr_risk(
    params: ParamValues,
    *,
    sizing: SizingRule | None = None,
    exit_at_time: str | None = None,
    no_entry_after: str | None = None,
) -> RiskRules:
    """Build ``RiskRules`` from the ATR-based parameter set."""
    stop = _atr_or_none(params, "stop_atr_multiple")
    target: LevelRule | None = None
    if stop is not None:
        multiple = params.number("target_r_multiple")
        target = RMultipleDistance(multiple) if multiple > 0 else None
    trailing_config = _trailing_config_from_params(params)
    return RiskRules(
        sizing=sizing or PercentOfEquity(params.number("capital_pct")),
        stop_loss=stop,
        take_profit=target,
        trailing_stop=None if trailing_config else _atr_or_none(params, "trailing_atr_multiple"),
        trailing_config=trailing_config,
        max_bars_in_trade=_positive_or_none(params, "max_bars_in_trade"),
        exit_at_time=exit_at_time,
        no_entry_after=no_entry_after,
        atr_period=params.integer("atr_period"),
        fractional_quantity=_flag(params, "fractional_quantity"),
    )


def _percent_or_none(params: ParamValues, name: str) -> LevelRule | None:
    if name not in params:
        return None
    value = params.number(name)
    return PercentDistance(value) if value > 0 else None


def _atr_or_none(params: ParamValues, name: str) -> LevelRule | None:
    if name not in params:
        return None
    value = params.number(name)
    return AtrDistance(value) if value > 0 else None


def _positive_or_none(params: ParamValues, name: str) -> int | None:
    if name not in params:
        return None
    value = params.integer(name)
    return value if value > 0 else None


def _flag(params: ParamValues, name: str) -> bool:
    return params.flag(name) if name in params else False


def _trailing_config_from_params(params: ParamValues) -> TrailingStopConfig | None:
    if "enable_trailing_stop" not in params or not params.flag("enable_trailing_stop"):
        return None
    method = TrailingMethod(params.text("trailing_method").lower())
    if method is TrailingMethod.PERCENT:
        return TrailingStopConfig(method=method, percent=params.number("trailing_stop_percent"))
    if method is TrailingMethod.POINTS:
        return TrailingStopConfig(method=method, points=params.number("trailing_stop_points"))
    return TrailingStopConfig(
        method=method,
        atr_multiplier=params.number("trailing_stop_atr_multiplier"),
    )
