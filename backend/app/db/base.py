"""Declarative base and shared column mixins.

No tables are defined here or anywhere else yet - models arrive in Phase 1.
The naming convention matters now rather than later: Alembic uses it to name
constraints, and SQLite cannot rename an unnamed constraint afterwards.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import DateTime, MetaData, String
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.core.ids import new_id

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """A ``DateTime(timezone=True)`` that is always UTC and always aware.

    SQLite (this app's only supported database today) has no native tz-aware
    datetime type: SQLAlchemy's sqlite dialect stores the wall-clock digits of
    whatever datetime it is given and drops the offset, so a value written as
    aware UTC comes back *naive* on read. Every timestamp this application
    writes is already a UTC instant (``utcnow()``, or a bar epoch converted
    with ``tz=UTC``) - so a naive value read back is reattached as UTC rather
    than left ambiguous. Without this, FastAPI/Pydantic serialize the naive
    value without a ``Z``/offset suffix, and the browser's ``Date`` parser then
    reads that string as *local* time - silently shifting every timestamp by
    the viewer's UTC offset (a real 5:30 hour error for an IST browser).
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"Refusing to store a naive datetime: {value!r}")
        return value.astimezone(UTC)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        parsed = cast(datetime, value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)


class IdMixin:
    """ULID text primary key."""

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)


class TimestampMixin:
    """created_at / updated_at, maintained by the database session."""

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
