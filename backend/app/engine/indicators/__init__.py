"""Incremental indicator library.

Every indicator is fed one bar at a time (see ``base.py`` for why) and is a
pure function of the bars it has been shown - no I/O, no globals, no clock.
Import the classes directly, or resolve them by name through ``registry`` when
the caller only has a string.
"""

from app.engine.indicators.base import PRIMARY_OUTPUT, Indicator, RollingWindow
from app.engine.indicators.momentum import RateOfChange, RelativeStrengthIndex
from app.engine.indicators.registry import (
    IndicatorInfo,
    get_indicator,
    indicator_names,
    list_indicators,
)
from app.engine.indicators.session import (
    SESSION_TIMEZONES,
    OpeningRange,
    SessionClock,
    minutes_of_day,
    resolve_zone,
)
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
    true_range,
)
from app.engine.indicators.volume import (
    OnBalanceVolume,
    RollingVwap,
    SessionVwap,
    typical_price,
)

__all__ = [
    "PRIMARY_OUTPUT",
    "SESSION_TIMEZONES",
    "AverageTrueRange",
    "BollingerBands",
    "DonchianChannel",
    "ExponentialMovingAverage",
    "Indicator",
    "IndicatorInfo",
    "Macd",
    "OnBalanceVolume",
    "OpeningRange",
    "RateOfChange",
    "RelativeStrengthIndex",
    "RollingVwap",
    "RollingWindow",
    "SessionClock",
    "SessionVwap",
    "SimpleMovingAverage",
    "StandardDeviation",
    "SuperTrend",
    "WeightedMovingAverage",
    "get_indicator",
    "indicator_names",
    "list_indicators",
    "minutes_of_day",
    "resolve_zone",
    "true_range",
    "typical_price",
]
