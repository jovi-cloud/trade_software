"""SQN, Kelly, Z score and Edge Ratio, including their sample-size gates."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.analytics.metrics import analyse
from app.analytics.report import AnalyticsReport
from app.analytics.statistics import MIN_SAMPLE_TRADES
from tests.unit.analytics.conftest import make_input, pnl_trade


def _run(pnls: list[float]) -> AnalyticsReport:
    return analyse(
        make_input(
            trades=tuple(
                pnl_trade(index + 1, pnl, entry_day=index, exit_day=index + 1)
                for index, pnl in enumerate(pnls)
            ),
            closes=[100] * (len(pnls) + 1),
        )
    )


def _alternating(count: int) -> list[float]:
    return [100.0 if index % 2 == 0 else -50.0 for index in range(count)]


def test_sqn_needs_a_meaningful_sample() -> None:
    """sqrt(N) rewards trade count directly, so a tiny sample is suppressed."""
    small = _run(_alternating(MIN_SAMPLE_TRADES - 1))
    large = _run(_alternating(MIN_SAMPLE_TRADES))

    assert small.statistics.sqn is None
    assert large.statistics.sqn is not None


def test_sqn_matches_the_van_tharp_formula() -> None:
    pnls = _alternating(40)
    report = _run(pnls)

    values = np.array(pnls, dtype=np.float64)
    expected = math.sqrt(len(pnls)) * float(np.mean(values)) / float(np.std(values, ddof=1))
    assert report.statistics.sqn == pytest.approx(expected, rel=1e-4)


def test_sqn_is_undefined_when_every_trade_is_identical() -> None:
    """No dispersion means no denominator."""
    report = _run([100.0] * MIN_SAMPLE_TRADES)

    assert report.statistics.sqn is None


def test_kelly_follows_win_rate_and_payoff_ratio() -> None:
    report = _run(_alternating(10))

    # 50% win rate, average win 100, average loss 50, so payoff = 2.
    assert report.trades.win_rate_pct == 50.0
    assert report.returns.payoff_ratio == 2.0
    assert report.statistics.kelly_pct == pytest.approx((0.5 - 0.5 / 2.0) * 100)


def test_kelly_is_negative_when_the_edge_is_not_exploitable() -> None:
    report = _run([50.0, -100.0, 50.0, -100.0])

    assert report.statistics.kelly_pct is not None
    assert report.statistics.kelly_pct < 0


def test_kelly_is_undefined_without_a_losing_trade() -> None:
    report = _run([100.0, 200.0])

    assert report.statistics.kelly_pct is None


def test_z_score_needs_thirty_decisive_trades() -> None:
    small = _run(_alternating(MIN_SAMPLE_TRADES - 1))
    large = _run(_alternating(MIN_SAMPLE_TRADES))

    assert small.statistics.z_score is None
    assert large.statistics.z_score is not None


def test_perfectly_alternating_outcomes_give_a_strongly_positive_z() -> None:
    """Maximum runs means far less clustering than chance - a positive Z."""
    report = _run(_alternating(40))

    assert report.statistics.z_score is not None
    assert report.statistics.z_score > 1.96


def test_heavily_clustered_outcomes_give_a_negative_z() -> None:
    """Two long blocks means far fewer runs than chance - a negative Z."""
    report = _run([100.0] * 20 + [-50.0] * 20)

    assert report.statistics.z_score is not None
    assert report.statistics.z_score < -1.96


def test_z_score_is_undefined_when_one_outcome_never_occurs() -> None:
    report = _run([100.0] * 40)

    assert report.statistics.z_score is None


def test_edge_ratio_is_mean_mfe_over_mean_mae() -> None:
    report = analyse(
        make_input(
            trades=(pnl_trade(1, 10.0, entry_day=0, exit_day=3),),
            closes=[100, 120, 95, 110],
        )
    )

    assert report.trades.average_mfe is not None
    assert report.trades.average_mae is not None
    assert report.statistics.edge_ratio == pytest.approx(
        report.trades.average_mfe / report.trades.average_mae, rel=1e-6
    )
