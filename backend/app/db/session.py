"""Engine and session factory.

One engine per process. Sessions are short-lived and never shared across
threads - the job runner opens its own.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.pragmas import register_sqlite_pragmas

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def create_db_engine(settings: Settings) -> Engine:
    """Build a configured SQLAlchemy engine for the settings' database URL."""
    url = settings.sqlalchemy_url
    if url.startswith("sqlite"):
        # SQLite files live under data/, which must exist before connecting.
        settings.data_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        url,
        echo=False,
        future=True,
        # check_same_thread=False: the job runner uses a thread pool, and each
        # thread opens its own session. Sessions are never shared between them.
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )
    if url.startswith("sqlite"):
        register_sqlite_pragmas(engine)
    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_db_engine(get_settings())
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False
        )
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for non-request code (jobs, scripts)."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    """Release pooled connections. Called on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
