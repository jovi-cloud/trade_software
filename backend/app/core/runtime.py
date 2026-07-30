"""Frozen-runtime detection and bundle path resolution for packaged builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# backend/app/core/runtime.py -> backend/app/core -> backend/app -> backend -> <repo root>
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

APP_DIR_NAME = "TradingResearch"


def is_frozen() -> bool:
    """True when running inside a PyInstaller one-file or one-folder bundle."""
    return getattr(sys, "frozen", False) is True


def bundle_dir() -> Path:
    """Root of the extracted bundle (PyInstaller ``_MEIPASS``) or repo root in dev."""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return REPO_ROOT


def default_data_dir() -> Path:
    """User data directory. Dev uses repo ``data/``; frozen uses ``%LOCALAPPDATA%``."""
    if is_frozen():
        local_app_data = os.environ.get("LOCALAPPDATA")
        root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return root / APP_DIR_NAME / "data"
    return REPO_ROOT / "data"


def frontend_dist_dir() -> Path:
    """Built frontend assets: ``frontend/dist`` in dev, bundled ``frontend_dist`` when frozen."""
    if is_frozen():
        # PyInstaller onedir places datas next to the executable; onefile uses _MEIPASS.
        candidates = [
            Path(sys.executable).resolve().parent / "frontend_dist",
            bundle_dir() / "frontend_dist",
        ]
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        return candidates[0]
    return REPO_ROOT / "frontend" / "dist"


def seed_data_bundle_dir() -> Path:
    """Bundled first-run seed tree staged under ``packaging/seed_data`` at build time."""
    if is_frozen():
        candidates = [
            Path(sys.executable).resolve().parent / "seed_data",
            bundle_dir() / "seed_data",
        ]
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        return candidates[0]
    return REPO_ROOT / "packaging" / "seed_data"
