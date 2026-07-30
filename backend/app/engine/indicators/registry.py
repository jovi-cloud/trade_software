"""Name -> indicator factory, with the metadata the UI and docs read.

The registry exists so that "which indicators can I use?" has one answer that
the parameter editor, the generated documentation, and the strategy author all
read from. Registration is explicit rather than discovered: an indicator is a
piece of trading mathematics, and having exactly one list of them that a human
reviewed beats scanning modules for classes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from app.engine.indicators.base import Indicator
from app.engine.indicators.momentum import RateOfChange, RelativeStrengthIndex
from app.engine.indicators.session import OpeningRange
from app.engine.indicators.trend import (
    DonchianChannel,
    ExponentialMovingAverage,
    Macd,
    SimpleMovingAverage,
    SuperTrend,
    WeightedMovingAverage,
)
from app.engine.indicators.volatility import (
    AverageTrueRange,
    BollingerBands,
    StandardDeviation,
)
from app.engine.indicators.volume import OnBalanceVolume, RollingVwap, SessionVwap

IndicatorFactory = Callable[..., Indicator]


@dataclass(frozen=True, slots=True)
class IndicatorInfo:
    """What the UI and generated docs need to describe one indicator."""

    name: str
    label: str
    category: str
    description: str
    outputs: tuple[str, ...]
    arguments: tuple[str, ...]
    factory: IndicatorFactory

    def create(self, *args: object, **kwargs: object) -> Indicator:
        return self.factory(*args, **kwargs)


_INDICATORS: tuple[IndicatorInfo, ...] = (
    IndicatorInfo(
        name="sma",
        label="Simple Moving Average",
        category="trend",
        description="Arithmetic mean of the last N closes.",
        outputs=SimpleMovingAverage.outputs,
        arguments=("period", "source"),
        factory=SimpleMovingAverage,
    ),
    IndicatorInfo(
        name="ema",
        label="Exponential Moving Average",
        category="trend",
        description="Exponentially weighted mean, SMA-seeded for reproducibility.",
        outputs=ExponentialMovingAverage.outputs,
        arguments=("period", "source"),
        factory=ExponentialMovingAverage,
    ),
    IndicatorInfo(
        name="wma",
        label="Weighted Moving Average",
        category="trend",
        description="Linearly weighted mean; the newest close carries the most weight.",
        outputs=WeightedMovingAverage.outputs,
        arguments=("period", "source"),
        factory=WeightedMovingAverage,
    ),
    IndicatorInfo(
        name="macd",
        label="MACD",
        category="trend",
        description="Fast EMA minus slow EMA, with its own signal EMA and histogram.",
        outputs=Macd.outputs,
        arguments=("fast_period", "slow_period", "signal_period"),
        factory=Macd,
    ),
    IndicatorInfo(
        name="donchian",
        label="Donchian Channel",
        category="trend",
        description=(
            "Highest high and lowest low over N bars, optionally excluding the current bar."
        ),
        outputs=DonchianChannel.outputs,
        arguments=("period", "exclude_current"),
        factory=DonchianChannel,
    ),
    IndicatorInfo(
        name="supertrend",
        label="SuperTrend",
        category="trend",
        description="ATR-banded trailing trend line with a +1/-1 direction flag.",
        outputs=SuperTrend.outputs,
        arguments=("period", "multiplier"),
        factory=SuperTrend,
    ),
    IndicatorInfo(
        name="rsi",
        label="Relative Strength Index",
        category="momentum",
        description="Wilder's RSI over N closes, bounded 0-100.",
        outputs=RelativeStrengthIndex.outputs,
        arguments=("period",),
        factory=RelativeStrengthIndex,
    ),
    IndicatorInfo(
        name="roc",
        label="Rate of Change",
        category="momentum",
        description="Percent change over N bars (2.5 means 2.5%).",
        outputs=RateOfChange.outputs,
        arguments=("period",),
        factory=RateOfChange,
    ),
    IndicatorInfo(
        name="atr",
        label="Average True Range",
        category="volatility",
        description="Wilder-smoothed True Range; the basis for volatility-scaled stops.",
        outputs=AverageTrueRange.outputs,
        arguments=("period",),
        factory=AverageTrueRange,
    ),
    IndicatorInfo(
        name="stddev",
        label="Standard Deviation",
        category="volatility",
        description="Population standard deviation of the last N closes.",
        outputs=StandardDeviation.outputs,
        arguments=("period",),
        factory=StandardDeviation,
    ),
    IndicatorInfo(
        name="bbands",
        label="Bollinger Bands",
        category="volatility",
        description="SMA envelope at +/- K standard deviations, with %B and bandwidth.",
        outputs=BollingerBands.outputs,
        arguments=("period", "deviations"),
        factory=BollingerBands,
    ),
    IndicatorInfo(
        name="vwap",
        label="Session VWAP",
        category="volume",
        description="Volume-weighted average price, re-anchored at each session open.",
        outputs=SessionVwap.outputs,
        arguments=("timezone",),
        factory=SessionVwap,
    ),
    IndicatorInfo(
        name="rolling_vwap",
        label="Rolling VWAP",
        category="volume",
        description="Volume-weighted average price over a fixed window of bars.",
        outputs=RollingVwap.outputs,
        arguments=("period",),
        factory=RollingVwap,
    ),
    IndicatorInfo(
        name="obv",
        label="On-Balance Volume",
        category="volume",
        description="Running total of volume signed by the direction of the close.",
        outputs=OnBalanceVolume.outputs,
        arguments=(),
        factory=OnBalanceVolume,
    ),
    IndicatorInfo(
        name="opening_range",
        label="Opening Range",
        category="session",
        description="High and low of the first N minutes of each exchange-local session.",
        outputs=OpeningRange.outputs,
        arguments=("timezone", "session_start", "range_minutes"),
        factory=OpeningRange,
    ),
)

_BY_NAME: Mapping[str, IndicatorInfo] = {info.name: info for info in _INDICATORS}


def list_indicators() -> tuple[IndicatorInfo, ...]:
    """Every registered indicator, in declaration order."""
    return _INDICATORS


def get_indicator(name: str) -> IndicatorInfo:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise KeyError(
            f"Unknown indicator '{name}'; available: {', '.join(sorted(_BY_NAME))}"
        ) from None


def indicator_names() -> tuple[str, ...]:
    return tuple(_BY_NAME)
