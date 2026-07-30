"""Immutable audit record for each dataset import attempt."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.domain.enums import ImportStatus


class DataImport(Base, IdMixin, TimestampMixin):
    """Append-only log of every import attempt (ARCHITECTURE.md 3.2)."""

    __tablename__ = "data_imports"

    dataset_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("datasets.id"), nullable=False, index=True
    )
    dataset_version_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("dataset_versions.id"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    rows_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gaps_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ImportStatus.PROCESSING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Import date is created_at from TimestampMixin.
