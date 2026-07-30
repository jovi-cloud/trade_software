"""Backtest run persistence DTOs."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import BacktestRunStatus
from app.domain.explain import ExplainLayer, ExplainLevel
from app.engine.explain.serialize import event_from_dict
from app.schemas.analytics import AnalyticsReportRead
from app.schemas.backtest import (
    CandleRead,
    EquityPointRead,
    OrderRead,
    PerformanceMetricsRead,
    TradeMarkerRead,
    TradeRead,
)
from app.schemas.explain import ExplainEventRead
from app.services.backtest_run_research import research_completion_pct, research_timeline


class BacktestRunResearchFields(BaseModel):
    experiment_name: str | None = None
    hypothesis: str | None = None
    what_changed: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    conclusion: str | None = None
    next_experiment: str | None = None
    tags: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class BacktestRunResearchUpdate(BaseModel):
    """Editable research journal fields only — execution snapshots stay immutable."""

    experiment_name: str | None = None
    hypothesis: str | None = None
    what_changed: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    conclusion: str | None = None
    next_experiment: str | None = None
    tags: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class BacktestRunResearchTimeline(BaseModel):
    run_created: bool
    research_completed: bool
    conclusion_written: bool


#: A parameter value as it crosses the API, matching ParamValueRead.
ParamValueRead = bool | int | float | str


class BacktestRunListItem(BaseModel):
    id: str
    strategy_id: str
    strategy_name: str
    library_strategy_id: str | None = None
    dataset_id: str
    dataset_name: str
    dataset_version_id: str | None = None
    dataset_version_number: int | None = None
    dataset_import_id: str | None = None
    dataset_imported_at: datetime | None = None
    dataset_quality_score: int | None = None
    execution_completed_at: datetime
    net_profit: float
    win_rate_pct: float
    trade_count: int = Field(ge=0)
    # Denormalised analytics headlines, so the runs list can sort on any of them.
    # Null for a run recorded before analytics existed, until its detail page is
    # opened once and the report is rebuilt from its snapshot.
    total_return_pct: float | None = None
    cagr_pct: float | None = None
    max_drawdown_pct: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    exposure_pct: float | None = None
    status: BacktestRunStatus
    experiment_name: str | None
    research_completion_pct: int = Field(ge=0, le=100)
    created_at: datetime


class BacktestRunRead(BaseModel):
    id: str
    strategy_id: str
    strategy_name: str
    dataset_id: str
    dataset_name: str
    dataset_version_id: str | None = None
    dataset_version_number: int | None = None
    dataset_import_id: str | None = None
    dataset_imported_at: datetime | None = None
    dataset_quality_score: int | None = None
    engine_version: str
    execution_started_at: datetime
    execution_completed_at: datetime
    execution_time_ms: float = Field(ge=0)
    initial_capital: float
    commission: float = Field(ge=0)
    slippage: float = Field(ge=0)
    strategy_code_snapshot: str
    dataset_hash: str
    strategy_hash: str
    library_strategy_id: str | None = Field(
        default=None, description="Set when a built-in strategy produced this run"
    )
    library_strategy_version: str | None = None
    strategy_params: dict[str, ParamValueRead] | None = Field(
        default=None, description="Resolved parameter values a library run used"
    )
    bars_processed: int = Field(ge=0)
    trade_count: int = Field(ge=0)
    final_cash: float
    position_closed: bool
    metrics: PerformanceMetricsRead
    analytics: AnalyticsReportRead
    equity_history: list[EquityPointRead]
    entry_markers: list[TradeMarkerRead]
    exit_markers: list[TradeMarkerRead]
    candles: list[CandleRead]
    orders: list[OrderRead]
    trades: list[TradeRead]
    strategy_logs: list[str]
    warnings: list[str]
    errors: list[str]
    completed: bool
    #: The run's lifecycle only - loaded, started, finished - which is bounded
    #: at a handful of events however long the dataset is. The per-bar and
    #: per-trade log scales with the dataset and is served, filtered and paged,
    #: by ``GET /backtests/runs/{run_id}/events``; inlining it here cost 28 MB
    #: and 55,000 rendered rows on a single intraday run.
    lifecycle_events: list[ExplainEventRead] = Field(default_factory=list)
    explain_level: ExplainLevel = ExplainLevel.TRADES_ONLY
    #: Bars in this run's decision log, or 0 when it has none. Non-zero is what
    #: tells a client the ``/decisions`` endpoints will answer for this run.
    decision_log_rows: int = Field(default=0, ge=0)
    status: BacktestRunStatus
    error_message: str | None
    notes: str | None
    experiment_name: str | None
    hypothesis: str | None
    what_changed: str | None
    expected_result: str | None
    actual_result: str | None
    conclusion: str | None
    next_experiment: str | None
    tags: str | None
    rating: int | None = Field(default=None, ge=1, le=5)
    research_completion_pct: int = Field(ge=0, le=100)
    research_timeline: BacktestRunResearchTimeline
    created_at: datetime
    updated_at: datetime


def metrics_from_json(metrics_json: str) -> PerformanceMetricsRead:
    import json

    payload: dict[str, Any] = json.loads(metrics_json)
    return PerformanceMetricsRead.model_validate(payload)


def research_fields_from_row(run: Any) -> BacktestRunResearchFields:
    return BacktestRunResearchFields(
        experiment_name=run.experiment_name,
        hypothesis=run.hypothesis,
        what_changed=run.what_changed,
        expected_result=run.expected_result,
        actual_result=run.actual_result,
        conclusion=run.conclusion,
        next_experiment=run.next_experiment,
        tags=run.tags,
        rating=run.rating,
        notes=run.notes,
    )


def list_item_from_row(run: Any, strategy_name: str, dataset_name: str) -> BacktestRunListItem:
    metrics = metrics_from_json(run.metrics_json)
    return BacktestRunListItem(
        id=run.id,
        strategy_id=run.strategy_id,
        strategy_name=strategy_name,
        library_strategy_id=run.library_strategy_id,
        dataset_id=run.dataset_id,
        dataset_name=dataset_name,
        dataset_version_id=run.dataset_version_id,
        dataset_version_number=run.dataset_version_number,
        dataset_import_id=run.dataset_import_id,
        dataset_imported_at=run.dataset_imported_at,
        dataset_quality_score=run.dataset_quality_score,
        execution_completed_at=run.execution_completed_at,
        net_profit=metrics.net_profit,
        win_rate_pct=run.win_rate_pct if run.win_rate_pct is not None else metrics.win_rate_pct,
        trade_count=run.trade_count,
        total_return_pct=run.total_return_pct,
        cagr_pct=run.cagr_pct,
        max_drawdown_pct=run.max_drawdown_pct,
        sharpe=run.sharpe,
        sortino=run.sortino,
        calmar=run.calmar,
        profit_factor=run.profit_factor,
        expectancy=run.expectancy,
        exposure_pct=run.exposure_pct,
        status=run.status,
        experiment_name=run.experiment_name,
        research_completion_pct=research_completion_pct(run),
        created_at=run.created_at,
    )


def read_from_row(
    run: Any,
    strategy_name: str,
    dataset_name: str,
    *,
    analytics: AnalyticsReportRead,
) -> BacktestRunRead:
    """Map a run row plus its analytics report into the detail response.

    ``analytics`` is supplied by the service rather than derived here: a run
    saved before analytics existed needs its report rebuilt from the snapshot,
    which is a service concern, and these mapping functions stay pure.
    """
    import json

    metrics = metrics_from_json(run.metrics_json)
    equity_history = [
        EquityPointRead.model_validate(item) for item in json.loads(run.equity_history_json)
    ]
    entry_markers = [
        TradeMarkerRead.model_validate(item) for item in json.loads(run.entry_markers_json)
    ]
    exit_markers = [
        TradeMarkerRead.model_validate(item) for item in json.loads(run.exit_markers_json)
    ]
    timeline = research_timeline(run)
    research = research_fields_from_row(run)
    return BacktestRunRead(
        id=run.id,
        strategy_id=run.strategy_id,
        strategy_name=strategy_name,
        dataset_id=run.dataset_id,
        dataset_name=dataset_name,
        dataset_version_id=run.dataset_version_id,
        dataset_version_number=run.dataset_version_number,
        dataset_import_id=run.dataset_import_id,
        dataset_imported_at=run.dataset_imported_at,
        dataset_quality_score=run.dataset_quality_score,
        engine_version=run.engine_version,
        execution_started_at=run.execution_started_at,
        execution_completed_at=run.execution_completed_at,
        execution_time_ms=run.execution_time_ms,
        initial_capital=run.initial_capital,
        commission=run.commission,
        slippage=run.slippage,
        strategy_code_snapshot=run.strategy_code_snapshot,
        dataset_hash=run.dataset_hash,
        strategy_hash=run.strategy_hash,
        library_strategy_id=run.library_strategy_id,
        library_strategy_version=run.library_strategy_version,
        strategy_params=(
            None if run.strategy_params_json is None else json.loads(run.strategy_params_json)
        ),
        bars_processed=run.bars_processed,
        trade_count=run.trade_count,
        final_cash=run.final_cash,
        position_closed=run.position_closed,
        metrics=metrics,
        analytics=analytics,
        equity_history=equity_history,
        entry_markers=entry_markers,
        exit_markers=exit_markers,
        candles=[CandleRead.model_validate(item) for item in json.loads(run.candles_json)],
        orders=[OrderRead.model_validate(item) for item in json.loads(run.orders_json)],
        trades=[TradeRead.model_validate(item) for item in json.loads(run.trades_json)],
        strategy_logs=json.loads(run.strategy_logs_json),
        warnings=json.loads(run.warnings_json),
        errors=json.loads(run.errors_json),
        lifecycle_events=[
            ExplainEventRead.model_validate(asdict(event_from_dict(item)))
            for item in json.loads(run.explain_events_json)
            if item.get("layer") == ExplainLayer.SYSTEM.value
        ],
        explain_level=ExplainLevel(run.explain_level),
        decision_log_rows=run.decision_log_rows or 0,
        completed=run.status == BacktestRunStatus.COMPLETED,
        status=run.status,
        error_message=run.error_message,
        notes=research.notes,
        experiment_name=research.experiment_name,
        hypothesis=research.hypothesis,
        what_changed=research.what_changed,
        expected_result=research.expected_result,
        actual_result=research.actual_result,
        conclusion=research.conclusion,
        next_experiment=research.next_experiment,
        tags=research.tags,
        rating=research.rating,
        research_completion_pct=research_completion_pct(run),
        research_timeline=BacktestRunResearchTimeline.model_validate(timeline),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
