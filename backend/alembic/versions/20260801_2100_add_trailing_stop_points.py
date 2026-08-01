"""Add trailing stop chart overlay snapshot to backtest runs.

Revision ID: c4e8a1f92d07
Revises: f8a2c4e6b0d3
Create Date: 2026-08-01 21:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a1f92d07"
down_revision: str | None = "f8a2c4e6b0d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("backtest_runs") as batch:
        batch.add_column(
            sa.Column(
                "trailing_stop_points_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("backtest_runs") as batch:
        batch.drop_column("trailing_stop_points_json")
