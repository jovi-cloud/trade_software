"""Research journal completion helpers."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.backtest_run_research import research_completion_pct, research_timeline


def test_research_completion_pct_empty() -> None:
    run = SimpleNamespace(
        experiment_name=None,
        hypothesis=None,
        what_changed=None,
        expected_result=None,
        actual_result=None,
        conclusion=None,
        next_experiment=None,
        tags=None,
        rating=None,
    )
    assert research_completion_pct(run) == 0


def test_research_completion_pct_partial() -> None:
    run = SimpleNamespace(
        experiment_name="ORB v2",
        hypothesis="Breakouts work in the first hour",
        what_changed=None,
        expected_result=None,
        actual_result=None,
        conclusion=None,
        next_experiment=None,
        tags=None,
        rating=None,
    )
    assert research_completion_pct(run) == 22


def test_research_timeline_milestones() -> None:
    run = SimpleNamespace(
        experiment_name=None,
        hypothesis=None,
        what_changed=None,
        expected_result=None,
        actual_result=None,
        conclusion="Needs tighter stops",
        next_experiment=None,
        tags=None,
        rating=None,
    )
    timeline = research_timeline(run)
    assert timeline["run_created"] is True
    assert timeline["research_completed"] is False
    assert timeline["conclusion_written"] is True
