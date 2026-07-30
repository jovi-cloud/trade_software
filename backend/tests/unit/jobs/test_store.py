"""Unit tests for the in-memory job store."""

from __future__ import annotations

from app.domain.enums import JobStatus, JobType
from app.jobs.store import InMemoryJobStore


def test_request_cancel_marks_job_cancelled() -> None:
    store = InMemoryJobStore()
    record = store.create(job_type=JobType.BACKTEST, payload={})
    store.mark_running(record.id)

    store.request_cancel(record.id)

    assert store.is_cancel_requested(record.id) is True
    store.mark_cancelled(record.id)
    assert store.get(record.id).status == JobStatus.CANCELLED
