"""Persisted backtest run CRUD. Validate -> call service -> return."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DbSession, Paths
from app.domain.enums import BacktestRunStatus
from app.domain.explain import ExplainEventStatus, ExplainEventType, ExplainLayer
from app.schemas.backtest_run import (
    BacktestRunListItem,
    BacktestRunRead,
    BacktestRunResearchUpdate,
    list_item_from_row,
    read_from_row,
)
from app.schemas.common import Page
from app.schemas.comparison import (
    ComparisonReportRead,
    RunComparisonRequest,
    comparison_report_read,
)
from app.schemas.explain import (
    BarInspectionRead,
    DecisionLogRead,
    DecisionSummaryRead,
    ExplainEventFilter,
    ExplainEventRead,
    TradeInspectionRead,
)
from app.services.backtest_run_service import BacktestRunService
from app.services.comparison_service import ComparisonService
from app.services.explain_service import MAX_DECISION_WINDOW, ExplainService
from app.services.run_export_service import RunExportService

router = APIRouter(prefix="/backtests/runs", tags=["backtest-runs"])

SortField = Literal[
    "created_at",
    "execution_completed_at",
    "net_profit",
    "trade_count",
    "total_return_pct",
    "cagr_pct",
    "max_drawdown_pct",
    "sharpe",
    "sortino",
    "calmar",
    "profit_factor",
    "win_rate_pct",
    "expectancy",
    "exposure_pct",
]
SortOrder = Literal["asc", "desc"]
EventSortField = Literal["seq", "timestamp_ms", "bar_index", "event_type"]


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


@router.get(
    "/compare",
    response_model=ComparisonReportRead,
    summary="Compare multiple backtest runs",
)
def compare_backtest_runs_get(
    db: DbSession,
    paths: Paths,
    run_ids: list[str] = Query(..., min_length=2, max_length=10),
) -> ComparisonReportRead:
    service = ComparisonService(db, paths)
    report = service.compare_run_ids(run_ids)
    return comparison_report_read(report)


@router.post(
    "/compare",
    response_model=ComparisonReportRead,
    summary="Compare multiple backtest runs",
)
def compare_backtest_runs_post(
    payload: RunComparisonRequest,
    db: DbSession,
    paths: Paths,
) -> ComparisonReportRead:
    service = ComparisonService(db, paths)
    report = service.compare_run_ids(payload.run_ids)
    return comparison_report_read(report)


@router.get("/{run_id}/download", summary="Download a complete backtest run export")
def download_backtest_run(run_id: str, db: DbSession, paths: Paths) -> Response:
    content, filename = RunExportService(db, paths).build_zip(run_id)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{run_id}", response_model=BacktestRunRead, summary="Get a backtest run")
def get_backtest_run(run_id: str, db: DbSession, paths: Paths) -> BacktestRunRead:
    service = BacktestRunService(db, paths)
    run, strategy_name, dataset_name, dataset_timezone = service.get(run_id)
    return read_from_row(
        run,
        strategy_name,
        dataset_name,
        dataset_timezone=dataset_timezone,
        analytics=service.analytics_for(run),
    )


@router.patch("/{run_id}", response_model=BacktestRunRead, summary="Update run research journal")
def update_backtest_run_research(
    run_id: str, payload: BacktestRunResearchUpdate, db: DbSession, paths: Paths
) -> BacktestRunRead:
    service = BacktestRunService(db, paths)
    run = service.update_research(run_id, payload)
    row = service.get(run.id)
    return read_from_row(
        row[0],
        row[1],
        row[2],
        dataset_timezone=row[3],
        analytics=service.analytics_for(row[0]),
    )


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a backtest run",
)
def delete_backtest_run(run_id: str, db: DbSession, paths: Paths) -> Response:
    service = BacktestRunService(db, paths)
    service.delete(run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{run_id}/events",
    response_model=Page[ExplainEventRead],
    summary="List explainability events for a run",
)
def list_run_events(
    run_id: str,
    db: DbSession,
    paths: Paths,
    layer: ExplainLayer | None = None,
    event_type: ExplainEventType | None = None,
    trade_id: int | None = Query(default=None, ge=1),
    order_id: int | None = Query(default=None, ge=1),
    position_id: int | None = Query(default=None, ge=1),
    reason_code: str | None = None,
    status_filter: ExplainEventStatus | None = Query(default=None, alias="status"),
    q: str | None = None,
    timestamp_from_ms: int | None = Query(default=None, ge=0),
    timestamp_to_ms: int | None = Query(default=None, ge=0),
    bar_index: int | None = Query(default=None, ge=0),
    sort: EventSortField = "seq",
    order: SortOrder = "asc",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[ExplainEventRead]:
    service = ExplainService(db, paths)
    filters = ExplainEventFilter(
        layer=layer,
        event_type=event_type,
        trade_id=trade_id,
        order_id=order_id,
        position_id=position_id,
        reason_code=reason_code,
        status=status_filter,
        q=q,
        timestamp_from_ms=timestamp_from_ms,
        timestamp_to_ms=timestamp_to_ms,
        bar_index=bar_index,
    )
    items, total = service.list_events(
        run_id,
        filters=filters,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )
    return Page[ExplainEventRead](items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{run_id}/trades/{trade_id}",
    response_model=TradeInspectionRead,
    summary="Inspect a trade reconstructed from explainability events",
)
def get_run_trade(run_id: str, trade_id: int, db: DbSession, paths: Paths) -> TradeInspectionRead:
    service = ExplainService(db, paths)
    return service.get_trade(run_id, trade_id)


@router.get(
    "/{run_id}/trades/{trade_id}/events",
    response_model=Page[ExplainEventRead],
    summary="List explainability events linked to a trade",
)
def list_run_trade_events(
    run_id: str,
    trade_id: int,
    db: DbSession,
    paths: Paths,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[ExplainEventRead]:
    service = ExplainService(db, paths)
    items, total = service.list_trade_events(
        run_id,
        trade_id,
        limit=limit,
        offset=offset,
    )
    return Page[ExplainEventRead](items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{run_id}/bars/{bar_index}",
    response_model=BarInspectionRead,
    summary="Inspect a single bar with decision and execution context",
)
def get_run_bar(run_id: str, bar_index: int, db: DbSession, paths: Paths) -> BarInspectionRead:
    service = ExplainService(db, paths)
    return service.get_bar(run_id, bar_index)


@router.get(
    "/{run_id}/decisions",
    response_model=DecisionLogRead,
    summary="Read a window of the per-bar decision log",
)
def get_run_decisions(
    run_id: str,
    db: DbSession,
    paths: Paths,
    start: int = Query(default=0, ge=0, description="First bar index to return"),
    count: int = Query(default=100, ge=1, le=MAX_DECISION_WINDOW),
) -> DecisionLogRead:
    service = ExplainService(db, paths)
    return service.get_decisions(run_id, start=start, count=count)


@router.get(
    "/{run_id}/decisions/summary",
    response_model=DecisionSummaryRead,
    summary="Whole-run condition tallies from the decision log",
)
def get_run_decision_summary(run_id: str, db: DbSession, paths: Paths) -> DecisionSummaryRead:
    service = ExplainService(db, paths)
    return service.get_decision_summary(run_id)


@router.get(
    "/{run_id}/bars/{bar_index}/events",
    response_model=Page[ExplainEventRead],
    summary="List explainability events for a single bar",
)
def list_run_bar_events(
    run_id: str,
    bar_index: int,
    db: DbSession,
    paths: Paths,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[ExplainEventRead]:
    service = ExplainService(db, paths)
    items, total = service.list_bar_events(
        run_id,
        bar_index,
        limit=limit,
        offset=offset,
    )
    return Page[ExplainEventRead](items=items, total=total, limit=limit, offset=offset)
