"""SQLite connection pragmas.

SQLite defaults are conservative and, for this application, wrong:
- foreign_keys is OFF by default, so FK constraints would be silently ignored.
- journal_mode=DELETE blocks readers during writes; WAL lets the UI read while
  a backtest job writes.
- busy_timeout=0 makes concurrent access fail instantly instead of waiting.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from sqlalchemy import Engine, event

BUSY_TIMEOUT_MS = 5_000


def register_sqlite_pragmas(engine: Engine) -> None:
    """Apply pragmas to every new connection in the pool."""

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection: Any, _record: Any) -> None:
        if not isinstance(dbapi_connection, sqlite3.Connection):
            return  # not SQLite (e.g. an in-memory test double): nothing to do
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        finally:
            cursor.close()
