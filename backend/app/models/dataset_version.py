"""Immutable dataset version records.

Each import creates a new version. Parquet files are never overwritten.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, UTCDateTime
from app.domain.enums import DatasetVersionStatus


class DatasetVersion(Base, IdMixin, TimestampMixin):
    """One immutable snapshot of cleaned bars for a dataset."""

    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version"),)

    dataset_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("datasets.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    data_import_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("data_imports.id"), nullable=True, index=True
    )

    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parquet_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_date: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    detected_timeframe: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # JSON-encoded PipelineReport.
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DatasetVersionStatus.VALIDATING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
