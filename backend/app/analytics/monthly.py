"""Calendar-month return breakdown — the monthly heatmap's data.

Grouping and the compounding rule live in ``periods.py``; this module only names
the result.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analytics.equity import DailySeries
from app.analytics.periods import aggregate_periods


@dataclass(frozen=True, slots=True)
class MonthlyReturn:
    """One calendar month of the run. ``month`` is 1-12."""

    year: int
    month: int
    return_pct: float
    pnl: float
    start_equity: float
    end_equity: float
    trading_days: int


def compute_monthly_returns(
    daily: DailySeries, *, initial_capital: float, timezone: str = "UTC"
) -> tuple[MonthlyReturn, ...]:
    """Month-by-month returns, ordered oldest first."""
    return tuple(
        MonthlyReturn(
            year=period.year,
            month=period.month,
            return_pct=period.return_pct,
            pnl=period.pnl,
            start_equity=period.start_equity,
            end_equity=period.end_equity,
            trading_days=period.trading_days,
        )
        for period in aggregate_periods(
            daily, initial_capital=initial_capital, by_month=True, timezone=timezone
        )
    )
