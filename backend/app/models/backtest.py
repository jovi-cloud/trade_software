"""BacktestRun ORM model.

Phase 4A: every completed execution becomes a permanent, immutable experiment
record. JSON snapshots store metrics and chart data exactly as returned by the
engine — never normalized into separate tables.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.domain.enums import BacktestRunStatus


class BacktestRun(Base, IdMixin, TimestampMixin):
    """An immutable snapshot of one strategy replay against one dataset."""

    __tablename__ = "backtest_runs"

    strategy_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("strategies.id"), nullable=False, index=True
    )
    dataset_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("datasets.id"), nullable=False, index=True
    )
    dataset_version_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("dataset_versions.id"), nullable=True, index=True
    )
    dataset_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataset_import_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("data_imports.id"), nullable=True
    )
    dataset_imported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dataset_quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    execution_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    execution_completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    execution_time_ms: Mapped[float] = mapped_column(Float, nullable=False)

    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    commission: Mapped[float] = mapped_column(Float, nullable=False)
    slippage: Mapped[float] = mapped_column(Float, nullable=False)

    strategy_code_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Null for a run of hand-written code. Populated for a library run so the
    # result can offer "run this again" and "back to the library entry" without
    # parsing them back out of the code snapshot.
    library_strategy_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    library_strategy_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    strategy_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    bars_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    final_cash: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    equity_history_json: Mapped[str] = mapped_column(Text, nullable=False)
    entry_markers_json: Mapped[str] = mapped_column(Text, nullable=False)
    exit_markers_json: Mapped[str] = mapped_column(Text, nullable=False)
    candles_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    orders_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    trades_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    strategy_logs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    errors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    explain_events_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    explain_level: Mapped[str] = mapped_column(String(20), nullable=False, default="trades_only")

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BacktestRunStatus.COMPLETED, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Phase 4B: optional research journal fields (editable; execution snapshots stay immutable).
    experiment_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_changed: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_experiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
