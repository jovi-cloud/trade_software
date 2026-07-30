"""add data pipeline fields and data_imports table

Revision ID: d8e2f4a5b6c7
Revises: c7d1e2f3a4b5
Created: 2026-07-30 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8e2f4a5b6c7"
down_revision: str | None = "c7d1e2f3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("original_filename", sa.String(length=500), nullable=True))
    op.add_column("datasets", sa.Column("file_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "datasets",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
    )
    op.add_column("datasets", sa.Column("detected_timeframe", sa.String(length=10), nullable=True))
    op.add_column("datasets", sa.Column("quality_score", sa.Integer(), nullable=True))

    op.create_table(
        "data_imports",
        sa.Column("dataset_id", sa.String(length=26), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("rows_read", sa.Integer(), nullable=False),
        sa.Column("rows_written", sa.Integer(), nullable=False),
        sa.Column("rows_rejected", sa.Integer(), nullable=False),
        sa.Column("duplicates_removed", sa.Integer(), nullable=False),
        sa.Column("gaps_detected", sa.Integer(), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("report_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name=op.f("fk_data_imports_dataset_id_datasets")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_imports")),
    )
    op.create_index(
        op.f("ix_data_imports_dataset_id"), "data_imports", ["dataset_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_data_imports_dataset_id"), table_name="data_imports")
    op.drop_table("data_imports")
    op.drop_column("datasets", "quality_score")
    op.drop_column("datasets", "detected_timeframe")
    op.drop_column("datasets", "timezone")
    op.drop_column("datasets", "file_hash")
    op.drop_column("datasets", "original_filename")
