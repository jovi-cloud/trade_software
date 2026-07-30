"""First-run seed data copy: bundled tree -> user data directory."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.core.runtime import seed_data_bundle_dir

logger = logging.getLogger(__name__)

_INITIALIZED_MARKER = ".initialized"


def _copy_tree(source: Path, destination: Path) -> None:
    """Recursively copy ``source`` into ``destination``, merging with existing files."""
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            _copy_tree(item, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def ensure_seed_data(data_dir: Path) -> None:
    """On first launch, copy bundled seed data into the user's data directory."""
    marker = data_dir / _INITIALIZED_MARKER
    if marker.exists():
        return

    bundle_seed = seed_data_bundle_dir()
    if not bundle_seed.is_dir() or not any(bundle_seed.iterdir()):
        logger.info("No bundled seed data at %s; creating empty data layout", bundle_seed)
        data_dir.mkdir(parents=True, exist_ok=True)
        for subdir in ("market", "artifacts", "imports", "logs"):
            (data_dir / subdir).mkdir(parents=True, exist_ok=True)
        marker.write_text("empty\n", encoding="utf-8")
        return

    logger.info("First run: copying seed data from %s to %s", bundle_seed, data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    _copy_tree(bundle_seed, data_dir)
    marker.write_text("seeded\n", encoding="utf-8")
    logger.info("Seed data copy complete")
