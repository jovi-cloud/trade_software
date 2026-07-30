"""Background job status."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import JobRunner
from app.jobs.store import JobRecord
from app.schemas.backtest import BacktestJobResultRead
from app.schemas.job import JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_read(record: JobRecord) -> JobRead:
    return JobRead(
        id=record.id,
        job_type=record.job_type,
        status=record.status,
        progress_pct=record.progress_pct,
        progress_message=record.progress_message,
        bars_processed=record.bars_processed,
        total_bars=record.total_bars,
        result=(
            BacktestJobResultRead.model_validate(record.result)
            if record.result is not None
            else None
        ),
        error_message=record.error_message,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


@router.get("/{job_id}", response_model=JobRead, summary="Get background job status")
def get_job(job_id: str, runner: JobRunner) -> JobRead:
    return _to_read(runner.get(job_id))


@router.post("/{job_id}/cancel", response_model=JobRead, summary="Cancel a running job")
def cancel_job(job_id: str, runner: JobRunner) -> JobRead:
    return _to_read(runner.cancel(job_id))
