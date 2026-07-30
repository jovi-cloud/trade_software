"""add the per-bar decision log to backtest runs

The log's rows live in a columnar artifact at
``artifacts/{run_id}/decisions.parquet``, located by convention rather than by a
stored path. What the database needs is only what the API must answer without
opening it: how many bars were logged, and the column layout together with the
per-run constants the rows were stripped of (condition names, their
expected-value prose, operand labels).

Existing runs get ``decision_log_rows = 0`` and a null schema, which is the
truthful record: they were executed before the log existed and there is no
artifact to point at. Runs are append-only, so they are not back-filled - a
re-run produces a new run with a log of its own.

Revision ID: b7d9f1a35c24
Revises: a2c4e6f80b13
Create Date: 2026-07-30 19:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7d9f1a35c24"
down_revision: str | None = "a2c4e6f80b13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backtest_runs",
        sa.Column("decision_log_rows", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_runs",
        sa.Column("decision_schema_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("backtest_runs", "decision_schema_json")
    op.drop_column("backtest_runs", "decision_log_rows")
