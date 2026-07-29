"""Run validation scenarios and build the developer validation report."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.domain.money import round_money
from app.engine.results.metrics import MetricsEngine
from app.engine.runner import ExecutionEngine
from app.engine.validation.hashing import hash_execution_result
from app.engine.validation.scenarios import VALIDATION_SCENARIOS, ValidationScenario
from app.engine.version import ENGINE_VERSION


@dataclass(frozen=True)
class ScenarioRunResult:
    name: str
    description: str
    passed: bool
    expected: dict[str, object]
    actual: dict[str, object]
    differences: tuple[str, ...]
    result_hash: str


@dataclass(frozen=True)
class DeterminismCheck:
    iterations: int
    passed: bool
    hashes: tuple[str, ...]


@dataclass(frozen=True)
class EngineValidationReport:
    engine_version: str
    scenario_count: int
    passed_count: int
    failed_count: int
    coverage_pct: float
    deterministic: DeterminismCheck
    scenarios: tuple[ScenarioRunResult, ...]
    calculation_summary: tuple[str, ...]
    dataset_validation_summary: tuple[str, ...]


def _compare(expected: float | int | bool, actual: float | int | bool, field: str) -> str | None:
    if isinstance(expected, bool):
        return None if expected == actual else f"{field}: expected {expected}, got {actual}"
    if round_money(float(expected)) != round_money(float(actual)):
        return f"{field}: expected {expected}, got {actual}"
    return None


def run_scenario(scenario: ValidationScenario) -> ScenarioRunResult:
    engine = ExecutionEngine(scenario.config)
    result = engine.run(strategy_source=scenario.strategy_source, bars=scenario.iterator())
    metrics, _ = MetricsEngine().compute(
        trades=list(result.trades),
        initial_capital=scenario.config.initial_capital,
        final_cash=result.final_cash,
    )
    gross_pnl = round_money(sum(trade.gross_pnl for trade in result.trades))
    actual = {
        "trade_count": result.trade_count,
        "final_cash": result.final_cash,
        "net_profit": metrics.net_profit,
        "gross_pnl": gross_pnl,
        "position_closed": result.position_closed,
    }
    expected = {
        "trade_count": scenario.expected.trade_count,
        "final_cash": scenario.expected.final_cash,
        "net_profit": scenario.expected.net_profit,
        "gross_pnl": scenario.expected.gross_pnl,
        "position_closed": scenario.expected.position_closed,
    }
    differences: list[str] = []
    for field, expected_value in expected.items():
        if expected_value is None:
            continue
        diff = _compare(expected_value, actual[field], field)
        if diff:
            differences.append(diff)

    cash_reconciled = round_money(
        scenario.config.initial_capital + sum(trade.net_pnl for trade in result.trades)
    )
    if result.position_closed and cash_reconciled != round_money(result.final_cash):
        differences.append(
            f"cash_reconciliation: expected {cash_reconciled}, got {result.final_cash}"
        )

    return ScenarioRunResult(
        name=scenario.name,
        description=scenario.description,
        passed=len(differences) == 0,
        expected=dict(expected),
        actual=dict(actual),
        differences=tuple(differences),
        result_hash=hash_execution_result(result, initial_capital=scenario.config.initial_capital),
    )


def check_determinism(*, iterations: int = 5) -> DeterminismCheck:
    scenario = VALIDATION_SCENARIOS[0]
    engine = ExecutionEngine(scenario.config)
    hashes: list[str] = []
    for _ in range(iterations):
        result = engine.run(strategy_source=scenario.strategy_source, bars=scenario.iterator())
        hashes.append(
            hash_execution_result(result, initial_capital=scenario.config.initial_capital)
        )
    return DeterminismCheck(
        iterations=iterations,
        passed=len(set(hashes)) == 1,
        hashes=tuple(hashes),
    )


def build_validation_report() -> EngineValidationReport:
    scenario_results = tuple(run_scenario(scenario) for scenario in VALIDATION_SCENARIOS)
    passed_count = sum(1 for result in scenario_results if result.passed)
    failed_count = len(scenario_results) - passed_count
    coverage_pct = round(passed_count / len(scenario_results) * 100, 2) if scenario_results else 0.0

    return EngineValidationReport(
        engine_version=ENGINE_VERSION,
        scenario_count=len(scenario_results),
        passed_count=passed_count,
        failed_count=failed_count,
        coverage_pct=coverage_pct,
        deterministic=check_determinism(),
        scenarios=scenario_results,
        calculation_summary=(
            "Fills occur at next bar open with slippage embedded in fill price.",
            "net_pnl = gross_pnl - commission; slippage is tracked separately for reporting.",
            "final_cash reconciles with initial_capital + sum(net_pnl) when flat.",
            "Money paths use Decimal internally via app.domain.money.",
        ),
        dataset_validation_summary=(
            "Import pipeline rejects invalid OHLC, negative volume, and non-positive prices.",
            "Parquet loads are validated strictly before engine execution.",
            "Duplicate and out-of-order timestamps are detected at import time.",
        ),
    )


def report_to_dict(report: EngineValidationReport) -> dict[str, object]:
    return asdict(report)
