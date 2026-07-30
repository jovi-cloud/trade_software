"""Thread-pool job runner."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.domain.enums import JobType
from app.jobs.handlers.backtest import run_backtest_job
from app.jobs.store import InMemoryJobStore, JobRecord

logger = logging.getLogger(__name__)


class ThreadPoolJobRunner:
    """Submit CPU-bound work to a bounded thread pool."""

    def __init__(
        self,
        settings: Settings,
        store: InMemoryJobStore | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or InMemoryJobStore()
        self._session_factory = session_factory
        self._executor = ThreadPoolExecutor(max_workers=settings.job_max_workers)

    @property
    def store(self) -> InMemoryJobStore:
        return self._store

    def submit_backtest(self, payload: dict[str, Any]) -> str:
        record = self._store.create(job_type=JobType.BACKTEST, payload=payload)
        self._executor.submit(
            run_backtest_job,
            record.id,
            payload,
            settings=self._settings,
            store=self._store,
            session_factory=self._session_factory,
        )
        return record.id

    def get(self, job_id: str) -> JobRecord:
        return self._store.get(job_id)

    def cancel(self, job_id: str) -> JobRecord:
        self._store.request_cancel(job_id)
        return self._store.get(job_id)

    def shutdown(self) -> None:
        logger.info("Shutting down job runner")
        self._executor.shutdown(wait=False, cancel_futures=True)
