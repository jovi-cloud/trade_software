"""Comparison engine unit tests."""

from __future__ import annotations

import pytest

from app.comparison import MAX_RUNS, MIN_RUNS, compare
from app.comparison.engine import _rank_values
from tests.unit.analytics.conftest import make_input, pnl_trade, trade
from tests.unit.comparison.conftest import compared_run


def test_two_run_comparison_produces_metric_matrix() -> None:
    run_a = compared_run("run-a", "A")
    run_b = compared_run("run-b", "B", analytics_input=make_input(closes=(100, 105, 110, 115, 120)))

    report = compare((run_a, run_b))

    assert report.run_count == 2
    assert len(report.metric_rows) >= 50
    first_profit = run_a.analytics.returns.net_profit
    second_profit = run_b.analytics.returns.net_profit
    assert report.metric_rows[0].values == (first_profit, second_profit)


def test_multi_run_comparison_supports_up_to_ten_runs() -> None:
    runs = tuple(compared_run(f"run-{index}", chr(65 + index)) for index in range(MAX_RUNS))
    report = compare(runs)
    assert report.run_count == MAX_RUNS
    assert all(len(row.values) == MAX_RUNS for row in report.metric_rows)


def test_too_few_runs_is_rejected() -> None:
    with pytest.raises(ValueError, match=str(MIN_RUNS)):
        compare((compared_run("only-one", "A"),))


def test_higher_is_better_picks_maximum() -> None:
    best, worst, tie = _rank_values([1.0, 3.0, 2.0], True)
    assert best == 1
    assert worst == 0
    assert tie is False


def test_lower_is_better_picks_minimum() -> None:
    best, worst, tie = _rank_values([5.0, 2.0, 8.0], False)
    assert best == 1
    assert worst == 2
    assert tie is False


def test_equal_metrics_are_marked_as_tie() -> None:
    same = make_input(
        trades=(
            trade(1, entry_day=0, exit_day=3, entry_price=100.0, exit_price=120.0),
            trade(2, entry_day=5, exit_day=8, entry_price=130.0, exit_price=135.0),
        ),
        closes=(100, 110, 105, 120, 115, 130, 125, 140, 135, 150),
    )
    row = compare(
        (
            compared_run("a", "A", analytics_input=same),
            compared_run("b", "B", analytics_input=same),
        )
    )
    tied = next(item for item in row.metric_rows if item.key == "net_profit")
    assert tied.is_tie is True
    assert tied.best_run_index is None


def test_missing_metrics_do_not_break_ranking() -> None:
    no_trades = make_input(closes=(100, 101, 102))
    row = compare(
        (
            compared_run("a", "A"),
            compared_run("b", "B", analytics_input=no_trades),
        )
    )
    net_profit = next(item for item in row.metric_rows if item.key == "net_profit")
    assert net_profit.values[0] is not None
    assert net_profit.values[1] == 0.0


def test_different_datasets_are_flagged() -> None:
    report = compare(
        (
            compared_run("a", "A", dataset_hash="hash-1"),
            compared_run("b", "B", dataset_hash="hash-2"),
        )
    )
    assert report.datasets_differ is True
    assert report.dataset_rows[1].differs_from_baseline is True


def test_strategy_parameter_diffs_show_only_changed_values() -> None:
    report = compare(
        (
            compared_run("a", "A", strategy_params={"fast": 10, "slow": 30}),
            compared_run("b", "B", strategy_params={"fast": 12, "slow": 30}),
        )
    )
    fast = next(item for item in report.strategy_parameter_diffs if item.name == "fast")
    slow = next(item for item in report.strategy_parameter_diffs if item.name == "slow")
    assert fast.differs is True
    assert slow.differs is False


def test_insights_reference_existing_metrics() -> None:
    better = make_input(
        trades=(pnl_trade(1, 50.0, entry_day=0, exit_day=2),),
        closes=(100, 105, 150),
    )
    worse = make_input(
        trades=(pnl_trade(1, -20.0, entry_day=0, exit_day=2),),
        closes=(100, 95, 80),
    )
    report = compare(
        (
            compared_run("a", "A", analytics_input=better),
            compared_run("b", "B", analytics_input=worse),
        )
    )
    assert report.insights
    assert all(insight.metric_key for insight in report.insights)
