"""Persisted backtest run CRUD. Validate -> call service -> return."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DbSession, Paths
from app.domain.enums import BacktestRunStatus
from app.schemas.backtest_run import (
    BacktestRunListItem,
    BacktestRunRead,
    BacktestRunResearchUpdate,
    list_item_from_row,
    read_from_row,
)
from app.schemas.common import Page
from app.services.backtest_run_service import BacktestRunService

router = APIRouter(prefix="/backtests/runs", tags=["backtest-runs"])

SortField = Literal["created_at", "execution_completed_at", "net_profit", "trade_count"]
SortOrder = Literal["asc", "desc"]


@router.get("", response_model=Page[BacktestRunListItem], summary="List backtest runs")
def list_backtest_runs(
    db: DbSession,
    paths: Paths,
    q: str | None = None,
    strategy_id: str | None = None,
    dataset_id: str | None = None,
    status_filter: BacktestRunStatus | None = Query(default=None, alias="status"),
    date_from: str | None = None,
    date_to: str | None = None,
    sort: SortField = "execution_completed_at",
    order: SortOrder = "desc",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[BacktestRunListItem]:
    service = BacktestRunService(db, paths)
    items, total = service.list(
        q=q,
        strategy_id=strategy_id,
        dataset_id=dataset_id,
        status=status_filter,
        date_from=service.parse_date_filter(date_from),
        date_to=service.parse_date_filter(date_to, end_of_day=True),
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )
    return Page[BacktestRunListItem](
        items=[
            list_item_from_row(run, strategy_name, dataset_name)
            for run, strategy_name, dataset_name in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}", response_model=BacktestRunRead, summary="Get a backtest run")
def get_backtest_run(run_id: str, db: DbSession, paths: Paths) -> BacktestRunRead:
    service = BacktestRunService(db, paths)
    run, strategy_name, dataset_name = service.get(run_id)
    return read_from_row(run, strategy_name, dataset_name)


@router.patch("/{run_id}", response_model=BacktestRunRead, summary="Update run research journal")
def update_backtest_run_research(
    run_id: str, payload: BacktestRunResearchUpdate, db: DbSession, paths: Paths
) -> BacktestRunRead:
    service = BacktestRunService(db, paths)
    run = service.update_research(run_id, payload)
    row = service.get(run.id)
    return read_from_row(row[0], row[1], row[2])


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a backtest run",
)
def delete_backtest_run(run_id: str, db: DbSession, paths: Paths) -> Response:
    service = BacktestRunService(db, paths)
    service.delete(run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
