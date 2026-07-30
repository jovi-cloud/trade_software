"""Comparison response DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.analytics.catalog import MetricCategory, MetricFormat
from app.comparison.report import ComparisonReport


class RunComparisonRequest(BaseModel):
    """Compare 2-10 completed runs side by side."""

    run_ids: list[str] = Field(min_length=2, max_length=10)


class ComparedRunSummaryRead(BaseModel):
    run_id: str
    label: str
    strategy_name: str
    dataset_name: str
    experiment_name: str | None


class MetricComparisonRowRead(BaseModel):
    key: str
    label: str
    category: MetricCategory
    format: MetricFormat
    precision: int
    description: str
    higher_is_better: bool | None
    values: list[float | None]
    best_run_index: int | None
    worst_run_index: int | None
    is_tie: bool
    spread: float | None
    spread_pct: float | None


class ResearchInsightRead(BaseModel):
    metric_key: str
    metric_label: str
    run_index: int
    run_id: str
    run_label: str
    value: float
    message: str


class StrategyParameterDiffRead(BaseModel):
    name: str
    values: list[Any]
    differs: bool


class DatasetComparisonRowRead(BaseModel):
    run_id: str
    run_label: str
    dataset_id: str
    dataset_name: str
    dataset_version_number: int | None
    dataset_hash: str
    dataset_imported_at: datetime | None
    dataset_quality_score: int | None
    differs_from_baseline: bool


class ExecutionComparisonRowRead(BaseModel):
    run_id: str
    run_label: str
    experiment_name: str | None
    engine_version: str
    execution_started_at: datetime
    execution_completed_at: datetime
    execution_time_ms: float
    bars_processed: int
    trade_count: int
    initial_capital: float
    commission: float
    slippage: float


class StrategyComparisonRowRead(BaseModel):
    run_id: str
    run_label: str
    strategy_id: str
    strategy_name: str
    strategy_hash: str
    library_strategy_id: str | None
    library_strategy_version: str | None
    strategy_params: dict[str, Any] | None
    differs_from_baseline: bool


class EquityOverlayPointRead(BaseModel):
    ts: int
    equity: float
    realised: float


class EquityOverlayRead(BaseModel):
    run_id: str
    run_label: str
    points: list[EquityOverlayPointRead]


class DrawdownOverlayPointRead(BaseModel):
    ts: int
    depth: float
    depth_pct: float


class DrawdownOverlayRead(BaseModel):
    run_id: str
    run_label: str
    points: list[DrawdownOverlayPointRead]
    max_drawdown_start_ts: int | None
    max_drawdown_trough_ts: int | None
    max_drawdown_recovery_ts: int | None


class MonthlyReturnOverlayRead(BaseModel):
    run_id: str
    run_label: str
    returns: list[dict[str, Any]]


class ComparisonReportRead(BaseModel):
    """Side-by-side comparison of multiple backtest runs."""

    comparison_version: str
    run_count: int
    runs: list[ComparedRunSummaryRead]
    metric_rows: list[MetricComparisonRowRead]
    insights: list[ResearchInsightRead]
    strategy_rows: list[StrategyComparisonRowRead]
    strategy_parameter_diffs: list[StrategyParameterDiffRead]
    dataset_rows: list[DatasetComparisonRowRead]
    execution_rows: list[ExecutionComparisonRowRead]
    equity_overlays: list[EquityOverlayRead]
    drawdown_overlays: list[DrawdownOverlayRead]
    monthly_returns_overlays: list[MonthlyReturnOverlayRead]
    datasets_differ: bool
    strategies_differ: bool


def comparison_report_read(report: ComparisonReport) -> ComparisonReportRead:
    from dataclasses import asdict

    payload = asdict(report)
    monthly = []
    for overlay in report.monthly_returns_overlays:
        monthly.append(
            {
                "run_id": overlay.run_id,
                "run_label": overlay.run_label,
                "returns": [asdict(item) for item in overlay.returns],
            }
        )
    payload["monthly_returns_overlays"] = monthly
    return ComparisonReportRead.model_validate(payload)
