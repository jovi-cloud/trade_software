"""Strategy Library CRUD. Validate -> call service -> return."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DbSession
from app.domain.enums import StrategyStatus
from app.schemas.common import Page
from app.schemas.strategy import StrategyCreate, StrategyRead, StrategyStats, StrategyUpdate
from app.services.strategy_service import StrategyService

router = APIRouter(prefix="/strategies", tags=["strategies"])

SortField = Literal["updated_at", "name"]
SortOrder = Literal["asc", "desc"]


@router.get("", response_model=Page[StrategyRead], summary="List strategies")
def list_strategies(
    db: DbSession,
    q: str | None = None,
    status_filter: StrategyStatus | None = Query(default=None, alias="status"),
    sort: SortField = "updated_at",
    order: SortOrder = "desc",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[StrategyRead]:
    service = StrategyService(db)
    items, total = service.list(
        q=q, status=status_filter, sort=sort, order=order, limit=limit, offset=offset
    )
    return Page[StrategyRead](
        items=[StrategyRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=StrategyStats, summary="Dashboard aggregate counts")
def get_strategy_stats(db: DbSession) -> StrategyStats:
    service = StrategyService(db)
    return StrategyStats.model_validate(service.stats())


@router.post(
    "",
    response_model=StrategyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a strategy",
)
def create_strategy(payload: StrategyCreate, db: DbSession) -> StrategyRead:
    service = StrategyService(db)
    return StrategyRead.model_validate(service.create(payload))


@router.get("/{strategy_id}", response_model=StrategyRead, summary="Get a strategy")
def get_strategy(strategy_id: str, db: DbSession) -> StrategyRead:
    service = StrategyService(db)
    return StrategyRead.model_validate(service.get(strategy_id))


@router.patch("/{strategy_id}", response_model=StrategyRead, summary="Update a strategy")
def update_strategy(strategy_id: str, payload: StrategyUpdate, db: DbSession) -> StrategyRead:
    service = StrategyService(db)
    return StrategyRead.model_validate(service.update(strategy_id, payload))


@router.delete(
    "/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft-delete a strategy"
)
def delete_strategy(strategy_id: str, db: DbSession) -> Response:
    service = StrategyService(db)
    service.delete(strategy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
