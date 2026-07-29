"""Dataset ORM model.

Phase 2A: the Dataset Library. One row per imported CSV. Deliberately flat -
no ``instruments`` table yet (mirrors ``Strategy.instrument`` being a plain
string in Phase 1B); the full ``datasets``/``data_imports`` split from
ARCHITECTURE.md 3.2 can arrive later without touching this shape.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.domain.enums import ImportStatus


class Dataset(Base, IdMixin, TimestampMixin):
    """An imported CSV of historical OHLCV bars, converted to Parquet."""

    __tablename__ = "datasets"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)

    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    import_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ImportStatus.PROCESSING
    )
    # JSON-encoded ValidationReport (app.data.validator); null while processing.
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
