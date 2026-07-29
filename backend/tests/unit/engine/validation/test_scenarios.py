"""Validation scenario suite."""

from __future__ import annotations

from app.engine.validation.runner import build_validation_report, run_scenario
from app.engine.validation.scenarios import VALIDATION_SCENARIOS


def test_all_validation_scenarios_pass() -> None:
    for scenario in VALIDATION_SCENARIOS:
        result = run_scenario(scenario)
        assert result.passed, f"{scenario.name}: {result.differences}"


def test_validation_report_is_fully_passing() -> None:
    report = build_validation_report()
    assert report.failed_count == 0
    assert report.coverage_pct == 100.0
    assert report.deterministic.passed is True
