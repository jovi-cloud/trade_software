"""Job request/response DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import JobStatus, JobType
from app.schemas.backtest import BacktestJobResultRead


class BacktestJobSubmitRead(BaseModel):
    """Accepted backtest job handle."""

    job_id: str = Field(min_length=1)


class JobRead(BaseModel):
    """Background job state for polling."""

    id: str
    job_type: JobType
    status: JobStatus
    progress_pct: float = Field(ge=0, le=100)
    progress_message: str = ""
    bars_processed: int | None = Field(default=None, ge=0)
    total_bars: int | None = Field(default=None, ge=0)
    result: BacktestJobResultRead | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
