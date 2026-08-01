"""Add persisted exchange session times to datasets.

Revision ID: f8a2c4e6b0d3
Revises: b7d9f1a35c24
Create Date: 2026-08-01 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8a2c4e6b0d3"
down_revision: str | None = "b7d9f1a35c24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("datasets") as batch_op:
        batch_op.add_column(
            sa.Column("session_open", sa.String(length=5), nullable=False, server_default="09:15")
        )
        batch_op.add_column(
            sa.Column("session_close", sa.String(length=5), nullable=False, server_default="15:25")
        )


def downgrade() -> None:
    with op.batch_alter_table("datasets") as batch_op:
        batch_op.drop_column("session_close")
        batch_op.drop_column("session_open")
