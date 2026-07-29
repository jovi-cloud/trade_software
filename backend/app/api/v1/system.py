"""System endpoints. The only routes implemented in Phase 0."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DbSession

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
