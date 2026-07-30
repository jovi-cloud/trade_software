"""add dataset lifecycle column

Revision ID: f1a2b3c4d5e6
Revises: e9f3a6b7c8d0
Create Date: 2026-07-30 15:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e9f3a6b7c8d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("lifecycle", sa.String(length=20), nullable=False, server_default="active")
        )


def downgrade() -> None:
    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.drop_column("lifecycle")
