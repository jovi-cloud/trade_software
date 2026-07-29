"""Identifier generation.

ULIDs: lexicographically sortable by creation time, no coordination needed,
safe to expose in URLs. Stored as 26-character text primary keys.
"""

from __future__ import annotations

from ulid import ULID


def new_id() -> str:
    """Generate a new ULID as a 26-character uppercase string."""
    return str(ULID())
