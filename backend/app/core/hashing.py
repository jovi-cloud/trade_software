"""Deterministic hashing of strategy code and dataset files."""

from __future__ import annotations

import hashlib
from pathlib import Path


def hash_text(text: str) -> str:
    """SHA-256 hex digest of UTF-8 text."""
    return hashlib.sha256(text.encode()).hexdigest()


def hash_file(path: Path) -> str:
    """SHA-256 hex digest of a file's raw bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()
