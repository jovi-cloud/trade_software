"""Strategy Library endpoints. Validate -> call service -> return.

## Why ``/strategy-library`` and not ``/strategies``

``/strategies`` is already taken by the user's own research strategies - rows in
the ``strategies`` table with ULID ids, full CRUD, and an existing
``POST /strategies/{id}/validate`` that checks *source code* syntax. Library
strategies are a different resource entirely: code-defined, read-only, addressed
by slug, and their ``validate`` checks *parameter values*. Mounting them on the
same path would either shadow those routes or make the meaning of an id depend
on which handler won, and both break existing clients. Separate prefix, no
collision, nothing existing changes.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.schemas.common import Page
from app.schemas.strategy_library import (
    LibraryFacetsRead,
    LibraryStrategyListItem,
    LibraryStrategyRead,
    ParameterSetRead,
    ParamValidateRequest,
    ParamValidationRead,
    StrategyDocumentationRead,
    to_detail,
    to_documentation,
    to_list_item,
    to_param_validation,
    to_parameter_set,
)
from app.services.strategy_library_service import StrategyLibraryService

router = APIRouter(prefix="/strategy-library", tags=["strategy-library"])

TradingStyle = Literal["intraday", "swing", "position"]


@router.get(
    "",
    response_model=Page[LibraryStrategyListItem],
    summary="List built-in strategies",
)
def list_library_strategies(
    q: str | None = Query(default=None, description="Free-text search"),
    category: str | None = None,
    tag: Annotated[list[str] | None, Query(description="Repeatable; all must match")] = None,
    market: str | None = None,
    timeframe: str | None = None,
    risk_level: str | None = None,
    style: TradingStyle | None = None,
    valid_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[LibraryStrategyListItem]:
    service = StrategyLibraryService()
    items, total = service.search(
        q=q,
        category=category,
        tags=tag or [],
        market=market,
        timeframe=timeframe,
        risk_level=risk_level,
        style=style,
        valid_only=valid_only,
        limit=limit,
        offset=offset,
    )
    return Page[LibraryStrategyListItem](
        items=[to_list_item(definition) for definition in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# Registered before /{strategy_id} so "facets" is never read as a strategy id.
@router.get(
    "/facets",
    response_model=LibraryFacetsRead,
    summary="Filter counts and any modules that failed to load",
)
def get_library_facets() -> LibraryFacetsRead:
    service = StrategyLibraryService()
    return LibraryFacetsRead.model_validate(service.facets())


@router.get(
    "/{strategy_id}",
    response_model=LibraryStrategyRead,
    summary="Get one built-in strategy",
)
def get_library_strategy(strategy_id: str) -> LibraryStrategyRead:
    service = StrategyLibraryService()
    return to_detail(service.get(strategy_id))


@router.get(
    "/{strategy_id}/parameters",
    response_model=ParameterSetRead,
    summary="Parameter contract, grouped for the generated editor",
)
def get_library_strategy_parameters(strategy_id: str) -> ParameterSetRead:
    service = StrategyLibraryService()
    return to_parameter_set(service.get(strategy_id))


@router.get(
    "/{strategy_id}/documentation",
    response_model=StrategyDocumentationRead,
    summary="Documentation generated from the strategy's declaration",
)
def get_library_strategy_documentation(strategy_id: str) -> StrategyDocumentationRead:
    service = StrategyLibraryService()
    return to_documentation(
        service.documentation(strategy_id), service.documentation_markdown(strategy_id)
    )


@router.post(
    "/{strategy_id}/validate",
    response_model=ParamValidationRead,
    summary="Validate parameter values without running the strategy",
)
def validate_library_strategy_params(
    strategy_id: str, payload: ParamValidateRequest
) -> ParamValidationRead:
    service = StrategyLibraryService()
    report = service.validate_params(strategy_id, payload.params)
    return to_param_validation(strategy_id, report)
