"""add immutable dataset versions and backtest lineage

Revision ID: e9f3a6b7c8d0
Revises: d8e2f4a5b6c7
Create Date: 2026-07-30 14:00:00.000000

"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision: str = "e9f3a6b7c8d0"
down_revision: str | None = "d8e2f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_versions",
        sa.Column("dataset_id", sa.String(length=26), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("data_import_id", sa.String(length=26), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("parquet_hash", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("detected_timeframe", sa.String(length=10), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("report_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["data_import_id"],
            ["data_imports.id"],
            name=op.f("fk_dataset_versions_data_import_id_data_imports"),
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name=op.f("fk_dataset_versions_dataset_id_datasets")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_versions")),
        sa.UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version"),
    )
    op.create_index(
        op.f("ix_dataset_versions_dataset_id"), "dataset_versions", ["dataset_id"], unique=False
    )
    op.create_index(
        op.f("ix_dataset_versions_data_import_id"),
        "dataset_versions",
        ["data_import_id"],
        unique=False,
    )

    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("current_version_id", sa.String(length=26), nullable=True))
        batch_op.add_column(sa.Column("current_version_number", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="uploaded")
        )

    with op.batch_alter_table("data_imports", schema=None) as batch_op:
        batch_op.add_column(sa.Column("dataset_version_id", sa.String(length=26), nullable=True))
        batch_op.create_index(
            op.f("ix_data_imports_dataset_version_id"),
            ["dataset_version_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            op.f("fk_data_imports_dataset_version_id_dataset_versions"),
            "dataset_versions",
            ["dataset_version_id"],
            ["id"],
        )

    with op.batch_alter_table("backtest_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("dataset_version_id", sa.String(length=26), nullable=True))
        batch_op.add_column(sa.Column("dataset_version_number", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("dataset_import_id", sa.String(length=26), nullable=True))
        batch_op.add_column(
            sa.Column("dataset_imported_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("dataset_quality_score", sa.Integer(), nullable=True))
        batch_op.create_index(
            op.f("ix_backtest_runs_dataset_version_id"),
            ["dataset_version_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            op.f("fk_backtest_runs_dataset_version_id_dataset_versions"),
            "dataset_versions",
            ["dataset_version_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            op.f("fk_backtest_runs_dataset_import_id_data_imports"),
            "data_imports",
            ["dataset_import_id"],
            ["id"],
        )

    _backfill_existing_data()


def _backfill_existing_data() -> None:
    bind = op.get_bind()
    datasets = bind.execute(
        sa.text(
            "SELECT id, file_path, row_count, start_date, end_date, timezone, "
            "detected_timeframe, quality_score, validation_errors, import_status, "
            "file_hash, created_at, updated_at FROM datasets"
        )
    ).mappings()

    for dataset in datasets:
        status = _map_import_status(dataset["import_status"])
        bind.execute(
            sa.text("UPDATE datasets SET status = :status WHERE id = :id"),
            {"status": status, "id": dataset["id"]},
        )

        if dataset["import_status"] != "completed" or not dataset["file_path"]:
            continue

        version_id = _new_ulid()
        file_path = dataset["file_path"]
        file_size = 0
        parquet_hash = ""
        fingerprint = dataset["file_hash"] or ""

        data_root = _resolve_data_root(bind)
        source = data_root / file_path
        version_path = data_root / "market" / dataset["id"] / "v1.parquet"
        if source.exists():
            version_path.parent.mkdir(parents=True, exist_ok=True)
            if source.resolve() != version_path.resolve():
                shutil.copy2(source, version_path)
            file_path = str(Path("market") / dataset["id"] / "v1.parquet")
            file_size = version_path.stat().st_size
            parquet_hash = _hash_file(version_path)
            fingerprint = parquet_hash

        bind.execute(
            sa.text(
                "INSERT INTO dataset_versions ("
                "id, dataset_id, version_number, data_import_id, file_path, file_size_bytes, "
                "parquet_hash, fingerprint, row_count, start_date, end_date, timezone, "
                "detected_timeframe, quality_score, report_json, status, error_message, "
                "created_at, updated_at"
                ") VALUES ("
                ":id, :dataset_id, 1, NULL, :file_path, :file_size_bytes, "
                ":parquet_hash, :fingerprint, :row_count, :start_date, :end_date, :timezone, "
                ":detected_timeframe, :quality_score, :report_json, 'valid', NULL, "
                ":created_at, :updated_at)"
            ),
            {
                "id": version_id,
                "dataset_id": dataset["id"],
                "file_path": file_path,
                "file_size_bytes": file_size,
                "parquet_hash": parquet_hash,
                "fingerprint": fingerprint,
                "row_count": dataset["row_count"],
                "start_date": dataset["start_date"],
                "end_date": dataset["end_date"],
                "timezone": dataset["timezone"] or "UTC",
                "detected_timeframe": dataset["detected_timeframe"],
                "quality_score": dataset["quality_score"],
                "report_json": dataset["validation_errors"],
                "created_at": dataset["created_at"],
                "updated_at": dataset["updated_at"],
            },
        )

        bind.execute(
            sa.text(
                "UPDATE datasets SET current_version_id = :version_id, "
                "current_version_number = 1, file_path = :file_path WHERE id = :dataset_id"
            ),
            {"version_id": version_id, "file_path": file_path, "dataset_id": dataset["id"]},
        )

        latest_import = (
            bind.execute(
                sa.text(
                    "SELECT id, created_at, quality_score FROM data_imports "
                    "WHERE dataset_id = :dataset_id ORDER BY created_at DESC LIMIT 1"
                ),
                {"dataset_id": dataset["id"]},
            )
            .mappings()
            .first()
        )

        if latest_import:
            bind.execute(
                sa.text(
                    "UPDATE dataset_versions SET data_import_id = :import_id WHERE id = :version_id"
                ),
                {"import_id": latest_import["id"], "version_id": version_id},
            )
            bind.execute(
                sa.text(
                    "UPDATE data_imports SET dataset_version_id = :version_id WHERE id = :import_id"
                ),
                {"version_id": version_id, "import_id": latest_import["id"]},
            )

        bind.execute(
            sa.text(
                "UPDATE backtest_runs SET dataset_version_id = :version_id, "
                "dataset_version_number = 1, dataset_import_id = :import_id, "
                "dataset_imported_at = :imported_at, dataset_quality_score = :quality_score "
                "WHERE dataset_id = :dataset_id"
            ),
            {
                "version_id": version_id,
                "import_id": latest_import["id"] if latest_import else None,
                "imported_at": latest_import["created_at"]
                if latest_import
                else dataset["created_at"],
                "quality_score": (
                    latest_import["quality_score"] if latest_import else dataset["quality_score"]
                ),
                "dataset_id": dataset["id"],
            },
        )


def _map_import_status(import_status: str) -> str:
    if import_status == "processing":
        return "validating"
    if import_status == "completed":
        return "valid"
    return "failed"


def _resolve_data_root(bind: sa.Connection) -> Path:
    row = bind.execute(sa.text("PRAGMA database_list")).mappings().first()
    if row and row["file"]:
        return Path(row["file"]).resolve().parent
    return Path("data")


def _hash_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _new_ulid() -> str:
    from app.core.ids import new_id

    return new_id()


def downgrade() -> None:
    with op.batch_alter_table("backtest_runs", schema=None) as batch_op:
        batch_op.drop_constraint(
            op.f("fk_backtest_runs_dataset_import_id_data_imports"), type_="foreignkey"
        )
        batch_op.drop_constraint(
            op.f("fk_backtest_runs_dataset_version_id_dataset_versions"), type_="foreignkey"
        )
        batch_op.drop_index(op.f("ix_backtest_runs_dataset_version_id"))
        batch_op.drop_column("dataset_quality_score")
        batch_op.drop_column("dataset_imported_at")
        batch_op.drop_column("dataset_import_id")
        batch_op.drop_column("dataset_version_number")
        batch_op.drop_column("dataset_version_id")

    with op.batch_alter_table("data_imports", schema=None) as batch_op:
        batch_op.drop_constraint(
            op.f("fk_data_imports_dataset_version_id_dataset_versions"), type_="foreignkey"
        )
        batch_op.drop_index(op.f("ix_data_imports_dataset_version_id"))
        batch_op.drop_column("dataset_version_id")

    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.drop_column("status")
        batch_op.drop_column("current_version_number")
        batch_op.drop_column("current_version_id")

    op.drop_index(op.f("ix_dataset_versions_data_import_id"), table_name="dataset_versions")
    op.drop_index(op.f("ix_dataset_versions_dataset_id"), table_name="dataset_versions")
    op.drop_table("dataset_versions")
