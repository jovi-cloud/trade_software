"""Golden regression test against a hand-verified reference dataset.

Every number below was computed by hand from the fixture before being written
here; the derivation is in the comments so a future failure can be judged rather
than blessed. If an unintended change moves a formula, this breaks loudly - which
is the point (ARCHITECTURE.md 9, golden-file test).

The fixture (``reference_input``): 10 daily bars closing
100, 110, 105, 120, 115, 130, 125, 140, 135, 150 on 10,000 of capital, with
two long trades of one unit each:

* trade 1: entry bar 0 @100, exit bar 3 @120  -> +20
* trade 2: entry bar 5 @130, exit bar 8 @135  -> +5
"""

from __future__ import annotations

import pytest

from app.analytics.inputs import AnalyticsInput
from app.analytics.metrics import ANALYTICS_VERSION, analyse
from tests.unit.analytics.conftest import INITIAL, ts_at


def test_reference_equity_curve(reference_input: AnalyticsInput) -> None:
    """Realised P&L lands on the exit bar; open bars mark to close.

    bar 0 flat @100 -> 10,000     bar 5 flat @130 -> 10,020
    bar 1 +10       -> 10,010     bar 6 -5        -> 10,015
    bar 2 +5        -> 10,005     bar 7 +10       -> 10,030
    bar 3 realised  -> 10,020     bar 8 realised  -> 10,025
    bar 4 flat      -> 10,020     bar 9 flat      -> 10,025
    """
    curve = analyse(reference_input).series.equity_curve

    assert [point.equity for point in curve] == [
        10_000.0,
        10_010.0,
        10_005.0,
        10_020.0,
        10_020.0,
        10_020.0,
        10_015.0,
        10_030.0,
        10_025.0,
        10_025.0,
    ]
    assert curve[0].ts == ts_at(0)
    assert curve[-1].ts == ts_at(9)


def test_reference_return_metrics(reference_input: AnalyticsInput) -> None:
    returns = analyse(reference_input).returns

    assert returns.net_profit == 25.0  # 20 + 5
    assert returns.gross_profit == 25.0
    assert returns.gross_loss == 0.0
    assert returns.total_return_pct == 0.25  # 25 / 10,000
    assert returns.average_trade == 12.5  # 25 / 2
    assert returns.average_win == 12.5
    assert returns.average_loss == 0.0
    assert returns.profit_factor is None  # no losing trade to divide by
    assert returns.payoff_ratio is None
    assert returns.final_equity == 10_025.0
    # Net profit 25 over a 5.0 maximum drawdown.
    assert returns.recovery_factor == 5.0


def test_reference_annualisation(reference_input: AnalyticsInput) -> None:
    """9 elapsed days: 0.25% linearly annualised, and compounded for CAGR."""
    returns = analyse(reference_input).returns

    assert returns.annualised_return_pct == pytest.approx(0.25 * 365.25 / 9, rel=1e-6)
    assert returns.cagr_pct == pytest.approx(
        ((10_025.0 / INITIAL) ** (365.25 / 9) - 1) * 100, rel=1e-6
    )


def test_reference_drawdown(reference_input: AnalyticsInput) -> None:
    """Three separate 5.0 setbacks: bars 2, 6, and 8-9 (never recovered)."""
    risk = analyse(reference_input).risk

    assert risk.max_drawdown == 5.0
    # Reported percentages are rounded to 6 decimals, so compare within half a
    # unit of the last place rather than relatively.
    assert risk.max_drawdown_pct == pytest.approx(5 / 10_010 * 100, abs=5e-7)
    assert risk.drawdown_episodes == 3
    assert risk.average_drawdown == 5.0


def test_reference_exposure(reference_input: AnalyticsInput) -> None:
    """In position on bars 0-2 and 5-7: 6 of 10 bars, 6 of 9 elapsed days."""
    risk = analyse(reference_input).risk

    assert risk.exposure_pct == 60.0
    assert risk.time_in_market_pct == pytest.approx(6 / 9 * 100, rel=1e-6)


def test_reference_trade_metrics(reference_input: AnalyticsInput) -> None:
    trades = analyse(reference_input).trades

    assert trades.total_trades == 2
    assert trades.winning_trades == 2
    assert trades.losing_trades == 0
    assert trades.win_rate_pct == 100.0
    assert trades.longest_win_streak == 2
    assert trades.longest_loss_streak == 0
    assert trades.average_bars_held == 3.0
    assert trades.largest_winner == 20.0
    assert trades.largest_loser == 0.0


def test_reference_excursions(reference_input: AnalyticsInput) -> None:
    """Highs are close+1 and lows close-1; the window includes the exit bar.

    trade 1 spans bars 0-3: best high 121, worst low 99, entry 100
            -> MFE 21, MAE 1
    trade 2 spans bars 5-8: best high 141, worst low 124, entry 130
            -> MFE 11, MAE 6
    """
    trades = analyse(reference_input).trades

    assert trades.average_mfe == 16.0  # (21 + 11) / 2
    assert trades.average_mae == 3.5  # (1 + 6) / 2
    assert analyse(reference_input).statistics.edge_ratio == pytest.approx(16.0 / 3.5, rel=1e-6)


def test_reference_capital_utilisation(reference_input: AnalyticsInput) -> None:
    """Notional over equity on each held bar, averaged across all ten.

    100/10,000 + 110/10,010 + 105/10,005 + 130/10,020 + 125/10,015 + 140/10,030
    """
    portfolio = analyse(reference_input).portfolio

    expected = (
        (100 / 10_000 + 110 / 10_010 + 105 / 10_005 + 130 / 10_020 + 125 / 10_015 + 140 / 10_030)
        / 10
        * 100
    )
    assert portfolio.capital_utilisation_pct == pytest.approx(expected, rel=1e-5)
    assert portfolio.peak_capital_utilisation_pct == pytest.approx(140 / 10_030 * 100, rel=1e-5)


def test_reference_calendar_tables(reference_input: AnalyticsInput) -> None:
    series = analyse(reference_input).series

    assert len(series.monthly_returns) == 1
    assert (series.monthly_returns[0].year, series.monthly_returns[0].month) == (2025, 1)
    assert series.monthly_returns[0].return_pct == 0.25
    assert len(series.yearly_returns) == 1
    assert series.yearly_returns[0].year == 2025
    assert series.yearly_returns[0].return_pct == 0.25


def test_reference_small_sample_statistics_are_suppressed(
    reference_input: AnalyticsInput,
) -> None:
    """Two trades cannot support SQN, Kelly or a runs test."""
    statistics = analyse(reference_input).statistics

    assert statistics.sqn is None
    assert statistics.kelly_pct is None
    assert statistics.z_score is None


def test_reference_meta_records_the_assumptions(reference_input: AnalyticsInput) -> None:
    meta = analyse(reference_input).meta

    assert meta.initial_capital == INITIAL
    assert meta.bar_count == 10
    assert meta.trade_count == 2
    assert meta.trading_days == 10
    assert meta.trading_days_per_year == 252
    assert meta.risk_free_rate_pct == 0.0
    assert meta.var_confidence_pct == 95.0
    assert meta.analytics_version == ANALYTICS_VERSION


def test_analysis_is_deterministic(reference_input: AnalyticsInput) -> None:
    """Two runs over identical input must be bit-for-bit identical."""
    first = analyse(reference_input)
    second = analyse(reference_input)

    assert first.metric_values() == second.metric_values()
    assert first.series.equity_curve == second.series.equity_curve
    assert first.series.monthly_returns == second.series.monthly_returns
