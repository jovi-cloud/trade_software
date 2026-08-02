"""Calendar-period aggregation of the daily equity series.

The compounding rule lives here so the monthly and yearly tables cannot drift
apart: **every period is measured against the previous period's closing
equity**, and the first against the starting capital. Consecutive period returns
therefore compound to the run's total return, which is what makes a monthly
heatmap or a yearly table safe to reason about.

Periods with no bars do not exist. A market holiday, a data gap, or a month the
dataset simply does not cover is absent from the table rather than reported as a
flat 0%.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.analytics import _numeric as num
from app.analytics.equity import DailySeries


@dataclass(frozen=True, slots=True)
class CalendarPeriod:
    """One aggregated calendar period. ``month`` is 0 for a yearly period."""

    year: int
    month: int
    return_pct: float
    pnl: float
    start_equity: float
    end_equity: float
    trading_days: int


def aggregate_periods(
    daily: DailySeries, *, initial_capital: float, by_month: bool, timezone: str = "UTC"
) -> tuple[CalendarPeriod, ...]:
    """Collapse daily equity into exchange-local calendar periods, oldest first.

    ``daily.day_ms`` is already the exchange-local midnight of each trading
    day (``build_daily_series``), expressed as a UTC instant - so it must be
    read back through the same ``timezone`` to recover the calendar year and
    month it actually belongs to.
    """
    if daily.is_empty:
        return ()

    zone = ZoneInfo(timezone)
    buckets: dict[tuple[int, int], list[int]] = {}
    for index, day_ms in enumerate(daily.day_ms.tolist()):
        moment = datetime.fromtimestamp(day_ms / 1000, tz=UTC).astimezone(zone)
        key = (moment.year, moment.month if by_month else 0)
        buckets.setdefault(key, []).append(index)

    periods: list[CalendarPeriod] = []
    previous_close = float(initial_capital)
    for key in sorted(buckets):
        indices = buckets[key]
        end_equity = float(daily.equity[indices[-1]])
        pnl = end_equity - previous_close
        periods.append(
            CalendarPeriod(
                year=key[0],
                month=key[1],
                return_pct=num.percent((num.divide(pnl, previous_close) or 0.0) * 100.0),
                pnl=num.money(pnl),
                start_equity=num.money(previous_close),
                end_equity=num.money(end_equity),
                trading_days=len(indices),
            )
        )
        previous_close = end_equity
    return tuple(periods)
