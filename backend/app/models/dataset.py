"""Dataset ORM model.

A dataset is the logical identity (instrument, exchange, timeframe). Immutable
bar data lives in ``dataset_versions``; denormalized fields here mirror the
current version for list views and backward-compatible APIs.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.domain.enums import DatasetLifecycle, DatasetStatus, ImportStatus


class Dataset(Base, IdMixin, TimestampMixin):
    """Logical dataset identity with a pointer to its current version."""

    __tablename__ = "datasets"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)

    current_version_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("dataset_versions.id"), nullable=True
    )
    current_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Denormalized from the current version for list/detail backward compatibility.
    file_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    original_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    detected_timeframe: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lifecycle: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DatasetLifecycle.ACTIVE
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DatasetStatus.UPLOADED
    )
    import_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ImportStatus.PROCESSING
    )
    # JSON-encoded PipelineReport; null while processing.
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
