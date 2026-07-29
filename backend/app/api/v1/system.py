"""System endpoints. The only routes implemented in Phase 0."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DbSession
from app.engine.validation.runner import build_validation_report, report_to_dict
from app.schemas.validation import EngineValidationReportRead

router = APIRouter(prefix="/system", tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: Literal["ok", "error"]


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
def health(db: DbSession) -> HealthResponse:
    """Confirms the API is up and the database is reachable."""
    try:
        db.execute(text("SELECT 1"))
        database: Literal["ok", "error"] = "ok"
    except Exception:  # health must always answer, never raise
        database = "error"

    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        version="0.1.0",
        database=database,
    )


@router.get(
    "/engine-validation",
    response_model=EngineValidationReportRead,
    summary="Developer engine validation report",
)
def engine_validation() -> EngineValidationReportRead:
    """Run deterministic validation scenarios and return pass/fail coverage."""
    report = build_validation_report()
    return EngineValidationReportRead.model_validate(report_to_dict(report))
