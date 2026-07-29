"""StrategyCode ORM model.

Phase 1C: the editable Python source for a strategy - one row per strategy
(unique FK). This is deliberately mutable; immutable ``strategy_versions``
(ARCHITECTURE.md 3.2) arrive in a later phase and are out of scope here.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class StrategyCode(Base, IdMixin, TimestampMixin):
    """The current Python source for a strategy, plus its last syntax check."""

    __tablename__ = "strategy_code"

    strategy_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("strategies.id"), nullable=False, unique=True
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    compiled_successfully: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    compile_error: Mapped[str | None] = mapped_column(Text, nullable=True)
