"""The comparison report: metric matrix, curves, diffs and insights."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.analytics.catalog import MetricCategory, MetricFormat
from app.analytics.monthly import MonthlyReturn
from app.analytics.portfolio import DrawdownPoint, EquityPoint


@dataclass(frozen=True, slots=True)
class MetricComparisonRow:
    """One metric across every compared run."""

    key: str
    label: str
    category: MetricCategory
    format: MetricFormat
    precision: int
    description: str
    higher_is_better: bool | None
    values: tuple[float | None, ...]
    best_run_index: int | None
    worst_run_index: int | None
    is_tie: bool
    spread: float | None
    spread_pct: float | None


@dataclass(frozen=True, slots=True)
class ResearchInsight:
    """A plain-language observation derived from an existing metric."""

    metric_key: str
    metric_label: str
    run_index: int
    run_id: str
    run_label: str
    value: float
    message: str


@dataclass(frozen=True, slots=True)
class StrategyParameterDiff:
    """One parameter and how it differs across runs."""

    name: str
    values: tuple[Any, ...]
    differs: bool


@dataclass(frozen=True, slots=True)
class DatasetComparisonRow:
    """Dataset lineage for one run."""

    run_id: str
    run_label: str
    dataset_id: str
    dataset_name: str
    dataset_version_number: int | None
    dataset_hash: str
    dataset_imported_at: datetime | None
    dataset_quality_score: int | None
    differs_from_baseline: bool


@dataclass(frozen=True, slots=True)
class ExecutionComparisonRow:
    """Execution metadata for one run."""

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


@dataclass(frozen=True, slots=True)
class StrategyComparisonRow:
    """Strategy identity for one run."""

    run_id: str
    run_label: str
    strategy_id: str
    strategy_name: str
    strategy_hash: str
    library_strategy_id: str | None
    library_strategy_version: str | None
    strategy_params: dict[str, Any] | None
    differs_from_baseline: bool


@dataclass(frozen=True, slots=True)
class EquityOverlay:
    run_id: str
    run_label: str
    points: tuple[EquityPoint, ...]


@dataclass(frozen=True, slots=True)
class DrawdownOverlay:
    run_id: str
    run_label: str
    points: tuple[DrawdownPoint, ...]
    max_drawdown_start_ts: int | None
    max_drawdown_trough_ts: int | None
    max_drawdown_recovery_ts: int | None


@dataclass(frozen=True, slots=True)
class MonthlyReturnsOverlay:
    run_id: str
    run_label: str
    returns: tuple[MonthlyReturn, ...]


@dataclass(frozen=True, slots=True)
class ComparedRunSummary:
    """Lightweight run header for the comparison UI."""

    run_id: str
    label: str
    strategy_name: str
    dataset_name: str
    experiment_name: str | None


@dataclass(frozen=True)
class ComparisonReport:
    """A complete side-by-side comparison of 2-10 runs."""

    comparison_version: str
    run_count: int
    runs: tuple[ComparedRunSummary, ...]
    metric_rows: tuple[MetricComparisonRow, ...]
    insights: tuple[ResearchInsight, ...]
    strategy_rows: tuple[StrategyComparisonRow, ...]
    strategy_parameter_diffs: tuple[StrategyParameterDiff, ...]
    dataset_rows: tuple[DatasetComparisonRow, ...]
    execution_rows: tuple[ExecutionComparisonRow, ...]
    equity_overlays: tuple[EquityOverlay, ...]
    drawdown_overlays: tuple[DrawdownOverlay, ...]
    monthly_returns_overlays: tuple[MonthlyReturnsOverlay, ...]
    datasets_differ: bool
    strategies_differ: bool
