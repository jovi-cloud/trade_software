"""Programmatic Alembic migrations for packaged (frozen) startup."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.core.runtime import bundle_dir, is_frozen

logger = logging.getLogger(__name__)


def _alembic_ini_path() -> Path:
    if is_frozen():
        return bundle_dir() / "alembic.ini"
    return bundle_dir() / "backend" / "alembic.ini"


def run_migrations() -> None:
    """Apply all pending migrations to the database configured in settings."""
    ini_path = _alembic_ini_path()
    if not ini_path.is_file():
        logger.warning("alembic.ini not found at %s; skipping migrations", ini_path)
        return

    config = Config(str(ini_path))
    if is_frozen():
        config.set_main_option("script_location", str(bundle_dir() / "alembic"))

    logger.info("Running database migrations")
    command.upgrade(config, "head")
    logger.info("Database migrations complete")
