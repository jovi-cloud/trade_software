"""Calendar-year return breakdown.

Same compounding rule as the monthly table (``monthly.py``): each year is
measured against the previous year's closing equity, so the yearly column
compounds to the run's total return.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analytics.equity import DailySeries
from app.analytics.periods import aggregate_periods


@dataclass(frozen=True, slots=True)
class YearlyReturn:
    """One calendar year of the run."""

    year: int
    return_pct: float
    pnl: float
    start_equity: float
    end_equity: float
    trading_days: int


def compute_yearly_returns(
    daily: DailySeries, *, initial_capital: float
) -> tuple[YearlyReturn, ...]:
    """Year-by-year returns, ordered oldest first."""
    return tuple(
        YearlyReturn(
            year=period.year,
            return_pct=period.return_pct,
            pnl=period.pnl,
            start_equity=period.start_equity,
            end_equity=period.end_equity,
            trading_days=period.trading_days,
        )
        for period in aggregate_periods(daily, initial_capital=initial_capital, by_month=False)
    )
