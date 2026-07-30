"""Backtest execution. Validate -> call service -> return."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from app.api.deps import DbSession, Paths
from app.db.base import utcnow
from app.engine.explain.serialize import event_to_dict
from app.engine.results.metrics import MetricsEngine
from app.engine.results.metrics_result import PerformanceMetrics
from app.engine.results.result import ExecutionResult
from app.schemas.backtest import (
    BacktestExecuteRequest,
    CandleRead,
    EquityPointRead,
    ExecutionResultRead,
    OrderRead,
    PerformanceMetricsRead,
    TradeMarkerRead,
    TradeRead,
)
from app.schemas.explain import ExplainEventRead
from app.services.backtest_run_service import BacktestRunService
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _metrics_read(
    metrics: PerformanceMetrics | None, initial_capital: float
) -> PerformanceMetricsRead:
    if metrics is None:
        metrics, _ = MetricsEngine().compute(
            trades=[],
            initial_capital=initial_capital,
            final_cash=initial_capital,
        )
    return PerformanceMetricsRead.model_validate(asdict(metrics))


def _to_response(
    result: ExecutionResult, *, initial_capital: float, run_id: str | None = None
) -> ExecutionResultRead:
    return ExecutionResultRead(
        run_id=run_id,
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
        metrics=_metrics_read(result.metrics, initial_capital),
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
        explain_events=[
            ExplainEventRead.model_validate(event_to_dict(event)) for event in result.explain_events
        ],
        explain_level=result.explain_level,
    )


@router.post(
    "/execute",
    response_model=ExecutionResultRead,
    summary="Replay a strategy against a dataset",
)
def execute_backtest(
    payload: BacktestExecuteRequest, db: DbSession, paths: Paths
) -> ExecutionResultRead:
    execution_service = ExecutionService(db, paths)
    run_service = BacktestRunService(db, paths)
    plan = execution_service.plan(
        dataset_id=payload.dataset_id,
        strategy_id=payload.strategy_id,
        library_strategy_id=payload.library_strategy_id,
        strategy_params=payload.strategy_params,
        initial_capital=payload.initial_capital,
        commission=payload.commission,
        slippage=payload.slippage,
        explain_level=payload.explain_level,
    )
    started_at = utcnow()
    result = execution_service.execute(
        strategy_id=plan.strategy_id,
        dataset_id=plan.dataset_id,
        config=plan.config,
        strategy=plan.strategy,
    )
    run = run_service.create_from_execution(
        strategy_id=plan.strategy_id,
        dataset_id=plan.dataset_id,
        config=plan.config,
        result=result,
        started_at=started_at,
        strategy_snapshot=plan.strategy.snapshot,
        library_strategy_id=plan.strategy.library_strategy_id,
        library_strategy_version=plan.strategy.library_strategy_version,
        strategy_params=plan.strategy.params or None,
    )
    return _to_response(result, initial_capital=plan.config.initial_capital, run_id=run.id)
