"""Bar builders for indicator tests.

Every fixture is hand-constructible so expected values can be worked out on
paper - which is the point: an indicator test that compares against another
implementation only proves the two agree.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.engine.bars import Bar
from app.engine.indicators.base import Indicator

MINUTE_MS = 60_000
DAY_MS = 86_400_000
#: 2024-01-01 00:00:00 UTC.
EPOCH_MS = 1_704_067_200_000


def bar(
    close: float,
    *,
    high: float | None = None,
    low: float | None = None,
    open_: float | None = None,
    volume: float = 1_000.0,
    ts: int = EPOCH_MS,
) -> Bar:
    return Bar(
        ts=ts,
        open=close if open_ is None else open_,
        high=close if high is None else high,
        low=close if low is None else low,
        close=close,
        volume=volume,
    )


def closes(values: Sequence[float], *, step_ms: int = DAY_MS) -> list[Bar]:
    """Flat bars where open == high == low == close, for pure close-series maths."""
    return [bar(value, ts=EPOCH_MS + index * step_ms) for index, value in enumerate(values)]


def ohlc(rows: Sequence[tuple[float, float, float, float]], *, step_ms: int = DAY_MS) -> list[Bar]:
    """Bars from explicit (open, high, low, close) tuples."""
    return [
        Bar(
            ts=EPOCH_MS + index * step_ms,
            open=row[0],
            high=row[1],
            low=row[2],
            close=row[3],
            volume=1_000.0,
        )
        for index, row in enumerate(rows)
    ]


def feed(indicator: Indicator, bars: Sequence[Bar]) -> list[float | None]:
    """Drive an indicator and collect its primary output per bar."""
    values: list[float | None] = []
    for one in bars:
        indicator.update(one)
        values.append(indicator.value)
    return values


@pytest.fixture
def rising_closes() -> list[Bar]:
    return closes([10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
