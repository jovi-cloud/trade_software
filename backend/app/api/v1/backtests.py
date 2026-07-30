"""Backtest execution. Validate -> call service -> return."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import DbSession, JobRunner, Paths
from app.schemas.backtest import BacktestExecuteRequest
from app.schemas.job import BacktestJobSubmitRead
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post(
    "/execute",
    response_model=BacktestJobSubmitRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Replay a strategy against a dataset",
)
def execute_backtest(
    payload: BacktestExecuteRequest, db: DbSession, paths: Paths, runner: JobRunner
) -> BacktestJobSubmitRead:
    execution_service = ExecutionService(db, paths)
    # Validate and resolve the container up front so rejected requests do not
    # enqueue work or leave half-created research records behind. The resolved
    # container id is passed through to the worker so it does not try to create
    # the same library container again in parallel.
    plan = execution_service.plan(
        dataset_id=payload.dataset_id,
        strategy_id=payload.strategy_id,
        library_strategy_id=payload.library_strategy_id,
        strategy_params=payload.strategy_params,
        initial_capital=payload.initial_capital,
        commission=payload.commission,
        slippage=payload.slippage,
        explain_level=payload.explain_level,
        dataset_version_id=payload.dataset_version_id,
        dataset_version_number=payload.dataset_version_number,
    )
    job_payload = payload.model_copy(update={"strategy_id": plan.strategy_id})
    job_id = runner.submit_backtest(job_payload.model_dump(mode="json"))
    return BacktestJobSubmitRead(job_id=job_id)
