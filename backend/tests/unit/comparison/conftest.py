"""Helpers for comparison unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.analytics.inputs import AnalyticsInput
from app.analytics.metrics import analyse
from app.comparison.inputs import ComparedRunInput
from tests.unit.analytics.conftest import make_input, trade


def _default_input() -> AnalyticsInput:
    return make_input(
        trades=(
            trade(1, entry_day=0, exit_day=3, entry_price=100.0, exit_price=120.0),
            trade(2, entry_day=5, exit_day=8, entry_price=130.0, exit_price=135.0),
        ),
        closes=(100, 110, 105, 120, 115, 130, 125, 140, 135, 150),
    )


def compared_run(
    run_id: str,
    label: str,
    *,
    analytics_input: AnalyticsInput | None = None,
    strategy_name: str = "Strategy",
    dataset_name: str = "Dataset",
    dataset_hash: str = "hash-a",
    strategy_hash: str = "strat-a",
    strategy_params: dict[str, Any] | None = None,
) -> ComparedRunInput:
    report = analyse(analytics_input or _default_input())
    now = datetime(2025, 1, 10, tzinfo=UTC)
    return ComparedRunInput(
        run_id=run_id,
        label=label,
        strategy_id=f"strategy-{label}",
        strategy_name=strategy_name,
        dataset_id=f"dataset-{label}",
        dataset_name=dataset_name,
        dataset_version_number=1,
        dataset_hash=dataset_hash,
        dataset_imported_at=now,
        dataset_quality_score=95,
        library_strategy_id=None,
        library_strategy_version=None,
        strategy_hash=strategy_hash,
        strategy_params=strategy_params,
        experiment_name=f"Experiment {label}",
        engine_version="1.0.0",
        execution_started_at=now,
        execution_completed_at=now,
        execution_time_ms=100.0,
        bars_processed=10,
        trade_count=report.trades.total_trades,
        initial_capital=10_000.0,
        commission=0.0,
        slippage=0.0,
        analytics=report,
    )
