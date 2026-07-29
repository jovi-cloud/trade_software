"""Strategy code editor endpoints. Validate -> call service -> return."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.strategy_code import (
    StrategyCodeRead,
    StrategyCodeUpdate,
    StrategyCodeValidateRequest,
    StrategyValidationResult,
)
from app.services.strategy_code_service import StrategyCodeService

router = APIRouter(prefix="/strategies", tags=["strategy-code"])


@router.get("/{strategy_id}/code", response_model=StrategyCodeRead, summary="Get strategy code")
def get_strategy_code(strategy_id: str, db: DbSession) -> StrategyCodeRead:
    service = StrategyCodeService(db)
    return StrategyCodeRead.model_validate(service.get_or_create(strategy_id))


@router.put("/{strategy_id}/code", response_model=StrategyCodeRead, summary="Save strategy code")
def update_strategy_code(
    strategy_id: str, payload: StrategyCodeUpdate, db: DbSession
) -> StrategyCodeRead:
    service = StrategyCodeService(db)
    return StrategyCodeRead.model_validate(service.update(strategy_id, payload.code))


@router.post(
    "/{strategy_id}/validate",
    response_model=StrategyValidationResult,
    summary="Check strategy code syntax (ast.parse only - never executed)",
)
def validate_strategy_code(
    strategy_id: str, payload: StrategyCodeValidateRequest, db: DbSession
) -> StrategyValidationResult:
    service = StrategyCodeService(db)
    return service.validate(strategy_id, payload.code)
