"""Strategy ORM model.

Phase 1B: strategy metadata plus the full research document (rules, risk
management, notes, confidence/priority). Still no ``strategy_versions`` and
no immutable-code rules - those arrive in a later phase (ARCHITECTURE.md 3.2).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.domain.enums import MarketType, Priority, StrategyStatus


class Strategy(Base, IdMixin, TimestampMixin):
    """A trading idea and the research document built around it."""

    __tablename__ = "strategies"
    __table_args__ = (
        CheckConstraint(
            "confidence_level >= 1 AND confidence_level <= 10", name="confidence_level_range"
        ),
    )

    # Research
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_type: Mapped[str] = mapped_column(String(20), nullable=False, default=MarketType.EQUITY)
    instrument: Mapped[str] = mapped_column(String(100), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)

    # Trading rules
    entry_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_rules: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Risk management
    stop_loss_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    position_sizing: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Research notes
    assumptions: Mapped[str | None] = mapped_column(Text, nullable=True)
    known_weaknesses: Mapped[str | None] = mapped_column(Text, nullable=True)
    ideas_for_improvement: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StrategyStatus.DRAFT)
    confidence_level: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default=Priority.MEDIUM)

    # Simple comma-separated string for V1; a normalised tags table (ARCHITECTURE.md
    # 3.2) can replace this without touching callers if tagging grows more complex.
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Soft delete: list/get/search exclude rows where this is set.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
