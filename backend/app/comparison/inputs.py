"""Inputs for run comparison — one row per run, analytics already computed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.analytics.report import AnalyticsReport


@dataclass(frozen=True, slots=True)
class ComparedRunInput:
    """Everything the comparison engine needs for one run."""

    run_id: str
    label: str
    strategy_id: str
    strategy_name: str
    dataset_id: str
    dataset_name: str
    dataset_version_number: int | None
    dataset_hash: str
    dataset_imported_at: datetime | None
    dataset_quality_score: int | None
    library_strategy_id: str | None
    library_strategy_version: str | None
    strategy_hash: str
    strategy_params: dict[str, Any] | None
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
    analytics: AnalyticsReport
