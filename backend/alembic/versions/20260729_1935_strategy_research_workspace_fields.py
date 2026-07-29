"""strategy research workspace fields

Revision ID: bd74062d9612
Revises: 42e367018b8e
Created: 2026-07-29 19:35:48.759749

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "bd74062d9612"
down_revision: str | None = "42e367018b8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("strategies", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("market_type", sa.String(length=20), nullable=False, server_default="equity")
        )
        # Nullable for the backfill below; tightened to NOT NULL once populated.
        batch_op.add_column(sa.Column("instrument", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("entry_rules", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("exit_rules", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("stop_loss_method", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("target_method", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("position_sizing", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("assumptions", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("known_weaknesses", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ideas_for_improvement", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("confidence_level", sa.Integer(), nullable=False, server_default="5")
        )
        batch_op.add_column(
            sa.Column("priority", sa.String(length=10), nullable=False, server_default="medium")
        )

    # market -> instrument: preserve any existing free-text market values.
    op.execute("UPDATE strategies SET instrument = market")

    with op.batch_alter_table("strategies", schema=None) as batch_op:
        batch_op.alter_column("instrument", existing_type=sa.String(length=100), nullable=False)
        batch_op.drop_column("market")
        batch_op.create_check_constraint(
            op.f("ck_strategies_confidence_level_range"),
            "confidence_level >= 1 AND confidence_level <= 10",
        )


def downgrade() -> None:
    with op.batch_alter_table("strategies", schema=None) as batch_op:
        batch_op.add_column(sa.Column("market", sa.VARCHAR(length=100), nullable=True))

    op.execute("UPDATE strategies SET market = instrument")

    with op.batch_alter_table("strategies", schema=None) as batch_op:
        batch_op.alter_column("market", existing_type=sa.String(length=100), nullable=False)
        batch_op.drop_constraint(op.f("ck_strategies_confidence_level_range"), type_="check")
        batch_op.drop_column("priority")
        batch_op.drop_column("confidence_level")
        batch_op.drop_column("ideas_for_improvement")
        batch_op.drop_column("known_weaknesses")
        batch_op.drop_column("assumptions")
        batch_op.drop_column("position_sizing")
        batch_op.drop_column("target_method")
        batch_op.drop_column("stop_loss_method")
        batch_op.drop_column("exit_rules")
        batch_op.drop_column("entry_rules")
        batch_op.drop_column("instrument")
        batch_op.drop_column("market_type")
