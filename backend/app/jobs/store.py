"""In-memory job state store.

Jobs are short-lived execution handles; persistence of the actual backtest
result lives on ``backtest_runs``. The store survives for the process lifetime
so the frontend can poll progress while a run is in flight.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.exceptions import NotFoundError
from app.core.ids import new_id
from app.db.base import utcnow
from app.domain.enums import JobStatus, JobType


@dataclass
class JobRecord:
    """One background job and its latest progress snapshot."""

    id: str
    job_type: JobType
    status: JobStatus
    progress_pct: float = 0.0
    progress_message: str = ""
    bars_processed: int | None = None
    total_bars: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error_message: str | None = None
    cancel_requested: bool = False
    created_at: datetime = field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class InMemoryJobStore:
    """Thread-safe job registry for the process-local runner."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create(self, *, job_type: JobType, payload: dict[str, Any]) -> JobRecord:
        record = JobRecord(
            id=new_id(),
            job_type=job_type,
            status=JobStatus.PENDING,
            payload=payload,
        )
        with self._lock:
            self._jobs[record.id] = record
        return record

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self._jobs.get(job_id)
        if record is None:
            raise NotFoundError(f"Job '{job_id}' not found")
        return record

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            record = self._require(job_id)
            record.status = JobStatus.RUNNING
            record.started_at = utcnow()

    def update_progress(
        self,
        job_id: str,
        *,
        progress_pct: float,
        progress_message: str,
        bars_processed: int | None = None,
        total_bars: int | None = None,
    ) -> None:
        with self._lock:
            record = self._require(job_id)
            record.progress_pct = min(100.0, max(0.0, progress_pct))
            record.progress_message = progress_message
            if bars_processed is not None:
                record.bars_processed = bars_processed
            if total_bars is not None:
                record.total_bars = total_bars

    def mark_completed(self, job_id: str, *, result: dict[str, Any]) -> None:
        with self._lock:
            record = self._require(job_id)
            record.status = JobStatus.COMPLETED
            record.progress_pct = 100.0
            record.progress_message = "Backtest complete"
            record.result = result
            record.finished_at = utcnow()

    def mark_failed(self, job_id: str, *, error_message: str) -> None:
        with self._lock:
            record = self._require(job_id)
            record.status = JobStatus.FAILED
            record.error_message = error_message
            record.progress_message = "Backtest failed"
            record.finished_at = utcnow()

    def request_cancel(self, job_id: str) -> None:
        with self._lock:
            record = self._require(job_id)
            if record.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
                return
            record.cancel_requested = True
            record.progress_message = "Cancelling…"

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            record = self._require(job_id)
            return record.cancel_requested

    def mark_cancelled(self, job_id: str) -> None:
        with self._lock:
            record = self._require(job_id)
            record.status = JobStatus.CANCELLED
            record.progress_message = "Backtest cancelled"
            record.finished_at = utcnow()

    def _require(self, job_id: str) -> JobRecord:
        record = self._jobs.get(job_id)
        if record is None:
            raise NotFoundError(f"Job '{job_id}' not found")
        return record
