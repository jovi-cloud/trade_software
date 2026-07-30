"""add explainability fields to backtest runs

Revision ID: a1b2c3d4e5f6
Revises: dbf5075675c4
Created: 2026-07-29 22:35:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "dbf5075675c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("backtest_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("explain_events_json", sa.Text(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column(
                "explain_level",
                sa.String(length=20),
                nullable=False,
                server_default="trades_only",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("backtest_runs", schema=None) as batch_op:
        batch_op.drop_column("explain_level")
        batch_op.drop_column("explain_events_json")
