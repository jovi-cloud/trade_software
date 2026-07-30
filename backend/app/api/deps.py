"""FastAPI dependencies.

Services are constructed here from Phase 1 onward; for now the database
session is the only shared dependency.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.paths import DataPaths, get_data_paths
from app.db.session import get_session_factory
from app.jobs.runner import ThreadPoolJobRunner


def get_db() -> Iterator[Session]:
    """Request-scoped session. The service layer owns commits, not this."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def get_paths(settings: Annotated[Settings, Depends(get_settings)]) -> DataPaths:
    return get_data_paths(settings)


def get_job_runner(request: Request) -> ThreadPoolJobRunner:
    runner = request.app.state.job_runner
    assert isinstance(runner, ThreadPoolJobRunner)
    return runner


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Paths = Annotated[DataPaths, Depends(get_paths)]
JobRunner = Annotated[ThreadPoolJobRunner, Depends(get_job_runner)]
