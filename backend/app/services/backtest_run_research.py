"""Research journal helpers for backtest runs."""

from __future__ import annotations

from typing import Any

RESEARCH_FIELDS = (
    "experiment_name",
    "hypothesis",
    "what_changed",
    "expected_result",
    "actual_result",
    "conclusion",
    "next_experiment",
    "tags",
    "rating",
)


def _is_filled(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def research_completion_pct(run: Any) -> int:
    """Share of research journal fields that have been filled (0-100)."""
    filled = sum(1 for field in RESEARCH_FIELDS if _is_filled(getattr(run, field)))
    return round(filled / len(RESEARCH_FIELDS) * 100)


def research_timeline(run: Any) -> dict[str, bool]:
    """Milestone flags for the run's research journal progress."""
    pct = research_completion_pct(run)
    return {
        "run_created": True,
        "research_completed": pct == 100,
        "conclusion_written": _is_filled(run.conclusion),
    }
