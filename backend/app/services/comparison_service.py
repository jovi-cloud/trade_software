"""Run comparison service — loads persisted runs and builds a comparison report."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.comparison._constants import MAX_RUNS, MIN_RUNS
from app.comparison.engine import RunComparison
from app.comparison.inputs import ComparedRunInput
from app.comparison.report import ComparisonReport
from app.core.exceptions import NotFoundError, ValidationError
from app.core.paths import DataPaths
from app.repositories.backtest_run_repo import BacktestRunRepository
from app.services.backtest_run_service import BacktestRunService

_RUN_LABELS = "ABCDEFGHIJ"


class ComparisonService:
    """Compares 2-10 completed runs using their stored analytics."""

    def __init__(
        self,
        session: Session,
        paths: DataPaths,
        *,
        comparison: RunComparison | None = None,
    ) -> None:
        self.session = session
        self.paths = paths
        self.runs = BacktestRunRepository(session)
        self.backtest_runs = BacktestRunService(session, paths)
        self.comparison = comparison or RunComparison()

    def compare_run_ids(self, run_ids: list[str]) -> ComparisonReport:
        unique = _dedupe_preserve_order(run_ids)
        if len(unique) < MIN_RUNS:
            raise ValidationError(f"At least {MIN_RUNS} distinct run IDs are required")
        if len(unique) > MAX_RUNS:
            raise ValidationError(f"At most {MAX_RUNS} runs can be compared at once")

        inputs: list[ComparedRunInput] = []
        for index, run_id in enumerate(unique):
            row = self.runs.get(run_id)
            if row is None:
                raise NotFoundError(f"Backtest run '{run_id}' not found")
            run, strategy_name, dataset_name = row
            analytics = self.backtest_runs.analytics_report_for(run)
            inputs.append(
                ComparedRunInput(
                    run_id=run.id,
                    label=_RUN_LABELS[index],
                    strategy_id=run.strategy_id,
                    strategy_name=strategy_name,
                    dataset_id=run.dataset_id,
                    dataset_name=dataset_name,
                    dataset_version_number=run.dataset_version_number,
                    dataset_hash=run.dataset_hash,
                    dataset_imported_at=run.dataset_imported_at,
                    dataset_quality_score=run.dataset_quality_score,
                    library_strategy_id=run.library_strategy_id,
                    library_strategy_version=run.library_strategy_version,
                    strategy_hash=run.strategy_hash,
                    strategy_params=(
                        None
                        if run.strategy_params_json is None
                        else json.loads(run.strategy_params_json)
                    ),
                    experiment_name=run.experiment_name,
                    engine_version=run.engine_version,
                    execution_started_at=run.execution_started_at,
                    execution_completed_at=run.execution_completed_at,
                    execution_time_ms=run.execution_time_ms,
                    bars_processed=run.bars_processed,
                    trade_count=run.trade_count,
                    initial_capital=run.initial_capital,
                    commission=run.commission,
                    slippage=run.slippage,
                    analytics=analytics,
                )
            )

        return self.comparison.compare(tuple(inputs))


def _dedupe_preserve_order(run_ids: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    result: list[str] = []
    for run_id in run_ids:
        cleaned = run_id.strip()
        if not cleaned or cleaned in seen:
            continue
        seen[cleaned] = None
        result.append(cleaned)
    return result
