"""Shared test fixtures.

Tests run against a real temporary SQLite file rather than mocks - integration
realism matters more than isolation for this application.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings pointed at a throwaway data directory."""
    return Settings(
        env="test",
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        log_to_file=False,
        log_level="WARNING",
    )


@pytest.fixture
def db_engine(settings: Settings) -> Iterator[Engine]:
    """A migrated engine isolated to this test's temp database.

    ``app.db.session`` caches one engine per process keyed off the global
    ``get_settings()`` singleton, which is the right call for a single-user
    desktop app but wrong for tests: it would otherwise point every test at
    the real ``data/app.db``. Building the engine directly here, and
    overriding ``get_db`` below, keeps each test on its own SQLite file.
    """
    from app.db.base import Base
    from app.db.session import create_db_engine

    engine = create_db_engine(settings)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    session = _session_factory(db_engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app(settings: Settings, db_engine: Engine) -> FastAPI:
    from app.api.deps import get_db
    from app.core.config import get_settings
    from app.main import create_app

    factory = _session_factory(db_engine)

    def _get_db_override() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    application = create_app(settings)
    application.dependency_overrides[get_db] = _get_db_override
    # get_settings() is process-wide (lru_cache): without this override, any
    # dependency chained off it (e.g. Paths) would resolve the real app.state
    # settings instead of this test's tmp_path, and tests would write into
    # the actual data/ directory.
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
