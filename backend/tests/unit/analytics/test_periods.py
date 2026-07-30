"""Monthly and yearly return tables."""

from __future__ import annotations

import pytest

from app.analytics.inputs import TradeRecord
from app.analytics.metrics import analyse
from app.analytics.report import AnalyticsReport
from tests.unit.analytics.conftest import INITIAL, make_input, pnl_trade


def _run_over_days(days: int, trades: tuple[TradeRecord, ...] = ()) -> AnalyticsReport:
    return analyse(make_input(trades=trades, closes=[100] * days))


def test_a_run_inside_one_month_produces_one_row() -> None:
    report = _run_over_days(10, (pnl_trade(1, 500.0, entry_day=0, exit_day=5),))
    monthly = report.series.monthly_returns

    assert len(monthly) == 1
    assert (monthly[0].year, monthly[0].month) == (2025, 1)
    assert monthly[0].return_pct == 5.0
    assert monthly[0].trading_days == 10


def test_months_are_measured_against_the_previous_month_close() -> None:
    """January +5%, February +5% on the new base - not on the original capital."""
    report = _run_over_days(
        60,
        (
            pnl_trade(1, 500.0, entry_day=5, exit_day=10),
            pnl_trade(2, 525.0, entry_day=35, exit_day=40),
        ),
    )
    monthly = {(row.year, row.month): row for row in report.series.monthly_returns}

    january = monthly[(2025, 1)]
    february = monthly[(2025, 2)]
    assert january.return_pct == 5.0
    assert january.end_equity == INITIAL + 500.0
    assert february.start_equity == january.end_equity
    assert february.return_pct == 5.0
    assert february.end_equity == INITIAL + 1_025.0


def test_monthly_returns_compound_to_the_total_return() -> None:
    report = _run_over_days(
        120,
        (
            pnl_trade(1, 800.0, entry_day=3, exit_day=8),
            pnl_trade(2, -300.0, entry_day=40, exit_day=45),
            pnl_trade(3, 1_200.0, entry_day=80, exit_day=90),
        ),
    )

    compounded = 1.0
    for row in report.series.monthly_returns:
        compounded *= 1.0 + row.return_pct / 100.0

    assert (compounded - 1.0) * 100 == pytest.approx(report.returns.total_return_pct, rel=1e-4)


def test_a_month_with_no_bars_is_absent_rather_than_flat() -> None:
    """A data gap must not read as a 0% month."""
    report = _run_over_days(20)
    months = {(row.year, row.month) for row in report.series.monthly_returns}

    assert months == {(2025, 1)}


def test_years_roll_over_and_compound_the_same_way() -> None:
    report = _run_over_days(
        420,
        (
            pnl_trade(1, 1_000.0, entry_day=10, exit_day=20),
            pnl_trade(2, 1_100.0, entry_day=380, exit_day=390),
        ),
    )
    yearly = {row.year: row for row in report.series.yearly_returns}

    assert set(yearly) == {2025, 2026}
    assert yearly[2025].return_pct == 10.0
    assert yearly[2026].start_equity == yearly[2025].end_equity
    assert yearly[2026].return_pct == 10.0


def test_yearly_returns_compound_to_the_total_return() -> None:
    report = _run_over_days(
        800,
        (
            pnl_trade(1, 1_000.0, entry_day=10, exit_day=20),
            pnl_trade(2, -500.0, entry_day=400, exit_day=410),
            pnl_trade(3, 2_000.0, entry_day=700, exit_day=750),
        ),
    )

    compounded = 1.0
    for row in report.series.yearly_returns:
        compounded *= 1.0 + row.return_pct / 100.0

    assert (compounded - 1.0) * 100 == pytest.approx(report.returns.total_return_pct, rel=1e-4)


def test_a_losing_month_reports_a_negative_return() -> None:
    report = _run_over_days(20, (pnl_trade(1, -750.0, entry_day=2, exit_day=6),))

    assert report.series.monthly_returns[0].return_pct == -7.5
    assert report.series.monthly_returns[0].pnl == -750.0


def test_no_bars_means_no_calendar_tables() -> None:
    report = analyse(make_input(trades=(), closes=[]))

    assert report.series.monthly_returns == ()
    assert report.series.yearly_returns == ()
    assert report.series.daily_pnl == ()
