"""add performance analytics to backtest runs

Adds the full analytics report as a JSON snapshot, plus the denormalised
headline metrics ARCHITECTURE.md 3.2 calls for so the runs list can sort on any
of them without reading a blob per row.

Every column is nullable. Existing runs keep their execution snapshot untouched
(runs are append-only); their report is rebuilt on read from the trades and
candles already stored, and the headline columns stay null for them rather than
being back-filled with numbers this migration cannot verify.

Revision ID: a2c4e6f80b13
Revises: f1a2b3c4d5e6
Create Date: 2026-07-30 17:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2c4e6f80b13"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HEADLINE_COLUMNS: tuple[str, ...] = (
    "total_return_pct",
    "cagr_pct",
    "max_drawdown_pct",
    "sharpe",
    "sortino",
    "calmar",
    "profit_factor",
    "win_rate_pct",
    "expectancy",
    "exposure_pct",
)


def upgrade() -> None:
    with op.batch_alter_table("backtest_runs") as batch:
        batch.add_column(sa.Column("analytics_json", sa.Text(), nullable=True))
        for column in HEADLINE_COLUMNS:
            batch.add_column(sa.Column(column, sa.Float(), nullable=True))

    # The runs list sorts by these; without the index a sort on Sharpe is a full
    # scan of every run ever recorded.
    op.create_index("ix_backtest_runs_sharpe", "backtest_runs", ["sharpe"])
    op.create_index("ix_backtest_runs_total_return_pct", "backtest_runs", ["total_return_pct"])
    op.create_index("ix_backtest_runs_max_drawdown_pct", "backtest_runs", ["max_drawdown_pct"])


def downgrade() -> None:
    op.drop_index("ix_backtest_runs_max_drawdown_pct", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_total_return_pct", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_sharpe", table_name="backtest_runs")

    with op.batch_alter_table("backtest_runs") as batch:
        for column in reversed(HEADLINE_COLUMNS):
            batch.drop_column(column)
        batch.drop_column("analytics_json")
