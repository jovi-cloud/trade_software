"""System validation report schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScenarioRunResultRead(BaseModel):
    name: str
    description: str
    passed: bool
    expected: dict[str, object]
    actual: dict[str, object]
    differences: list[str]
    result_hash: str


class DeterminismCheckRead(BaseModel):
    iterations: int
    passed: bool
    hashes: list[str]


class EngineValidationReportRead(BaseModel):
    engine_version: str
    scenario_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    coverage_pct: float = Field(ge=0, le=100)
    deterministic: DeterminismCheckRead
    scenarios: list[ScenarioRunResultRead]
    calculation_summary: list[str]
    dataset_validation_summary: list[str]
