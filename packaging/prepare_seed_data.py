#!/usr/bin/env python3
"""Stage first-run seed data under packaging/seed_data for the Windows installer.

Creates a migrated, WAL-checkpointed SQLite database and empty data subdirectories.
Run from the repository root before building the PyInstaller bundle:

    cd backend && uv run python ../packaging/prepare_seed_data.py
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# Allow running as a script from backend/ via uv.
BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_DEST = REPO_ROOT / "packaging" / "seed_data"
SUBDIRS = ("market", "artifacts", "imports", "logs")


def _checkpoint_wal(db_path: Path) -> None:
    """Flush WAL pages into the main DB file and remove sidecar files."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()

    for suffix in (".db-wal", ".db-shm"):
        sidecar = db_path.parent / f"{db_path.name}{suffix}"
        if sidecar.exists():
            sidecar.unlink()


def _migrate_database(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)

    db_path = data_dir / "app.db"
    if db_path.exists():
        db_path.unlink()

    # env.py resolves the URL from application settings, not alembic.ini.
    import os

    from app.core.config import get_settings

    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    get_settings.cache_clear()

    ini_path = BACKEND_ROOT / "alembic.ini"
    config = Config(str(ini_path))
    command.upgrade(config, "head")
    _checkpoint_wal(db_path)
    return db_path


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="seed_data_") as tmp:
        staging = Path(tmp) / "data"
        db_path = _migrate_database(staging)
        print(f"Migrated database: {db_path} ({db_path.stat().st_size} bytes)")

        if SEED_DEST.exists():
            shutil.rmtree(SEED_DEST)
        shutil.copytree(staging, SEED_DEST)

    print(f"Seed data staged at {SEED_DEST}")


if __name__ == "__main__":
    main()
