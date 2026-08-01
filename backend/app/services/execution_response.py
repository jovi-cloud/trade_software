"""Map engine execution results to API response models."""

from __future__ import annotations

from dataclasses import asdict

from app.engine.explain.serialize import event_to_dict
from app.engine.results.metrics import MetricsEngine
from app.engine.results.metrics_result import PerformanceMetrics
from app.engine.results.result import ExecutionResult
from app.schemas.analytics import AnalyticsReportRead
from app.schemas.backtest import (
    CandleRead,
    EquityPointRead,
    ExecutionResultRead,
    OrderRead,
    PerformanceMetricsRead,
    TradeMarkerRead,
    TradeRead,
    TrailingStopPointRead,
)
from app.schemas.explain import ExplainEventRead


def metrics_read(
    metrics: PerformanceMetrics | None, initial_capital: float
) -> PerformanceMetricsRead:
    if metrics is None:
        metrics, _ = MetricsEngine().compute(
            trades=[],
            initial_capital=initial_capital,
            final_cash=initial_capital,
        )
    return PerformanceMetricsRead.model_validate(asdict(metrics))


def execution_result_read(
    result: ExecutionResult,
    *,
    initial_capital: float,
    analytics: AnalyticsReportRead,
    run_id: str | None = None,
    dataset_version_id: str | None = None,
    dataset_version_number: int | None = None,
    dataset_fingerprint: str | None = None,
) -> ExecutionResultRead:
    return ExecutionResultRead(
        run_id=run_id,
        dataset_version_id=dataset_version_id,
        dataset_version_number=dataset_version_number,
        dataset_fingerprint=dataset_fingerprint,
        completed=result.completed,
        bars_processed=result.bars_processed,
        execution_time_ms=result.execution_time_ms,
        errors=list(result.errors),
        warnings=list(result.warnings),
        strategy_logs=list(result.strategy_logs),
        orders=[OrderRead.model_validate(asdict(order)) for order in result.orders],
        trades=[TradeRead.model_validate(asdict(trade)) for trade in result.trades],
        final_cash=result.final_cash,
        position_closed=result.position_closed,
        trade_count=result.trade_count,
        metrics=metrics_read(result.metrics, initial_capital),
        analytics=analytics,
        equity_history=[
            EquityPointRead.model_validate(asdict(point)) for point in result.equity_history
        ],
        candles=[CandleRead.model_validate(asdict(candle)) for candle in result.candles],
        entry_markers=[
            TradeMarkerRead.model_validate(asdict(marker)) for marker in result.entry_markers
        ],
        exit_markers=[
            TradeMarkerRead.model_validate(asdict(marker)) for marker in result.exit_markers
        ],
        trailing_stop_points=[
            TrailingStopPointRead.model_validate(asdict(point))
            for point in result.trailing_stop_points
        ],
        explain_events=[
            ExplainEventRead.model_validate(event_to_dict(event)) for event in result.explain_events
        ],
        explain_level=result.explain_level,
    )
