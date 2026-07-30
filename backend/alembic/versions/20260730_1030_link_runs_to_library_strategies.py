"""link backtest runs and research containers to library strategies

Additive and nullable throughout: every existing row keeps meaning exactly what
it meant before (a run of hand-written code, an idea the user typed in).

Revision ID: c7d1e2f3a4b5
Revises: a1b2c3d4e5f6
Created: 2026-07-30 10:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7d1e2f3a4b5"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("strategies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("library_strategy_id", sa.String(length=100), nullable=True))
        batch_op.create_index(
            "ix_strategies_library_strategy_id", ["library_strategy_id"], unique=False
        )

    with op.batch_alter_table("backtest_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("library_strategy_id", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("library_strategy_version", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(sa.Column("strategy_params_json", sa.Text(), nullable=True))
        batch_op.create_index(
            "ix_backtest_runs_library_strategy_id", ["library_strategy_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("backtest_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_backtest_runs_library_strategy_id")
        batch_op.drop_column("strategy_params_json")
        batch_op.drop_column("library_strategy_version")
        batch_op.drop_column("library_strategy_id")

    with op.batch_alter_table("strategies", schema=None) as batch_op:
        batch_op.drop_index("ix_strategies_library_strategy_id")
        batch_op.drop_column("library_strategy_id")
