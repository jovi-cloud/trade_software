"""The comparison engine — aligns metrics, curves and metadata across runs."""

from __future__ import annotations

from typing import Any

from app.analytics.catalog import METRIC_DEFINITIONS, MetricCategory
from app.comparison._constants import COMPARISON_VERSION, MAX_RUNS, MIN_RUNS
from app.comparison.inputs import ComparedRunInput
from app.comparison.insights import build_insights
from app.comparison.report import (
    ComparedRunSummary,
    ComparisonReport,
    DatasetComparisonRow,
    DrawdownOverlay,
    EquityOverlay,
    ExecutionComparisonRow,
    MetricComparisonRow,
    MonthlyReturnsOverlay,
    StrategyComparisonRow,
    StrategyParameterDiff,
)


class RunComparison:
    """Builds a comparison report from pre-computed analytics."""

    def compare(self, runs: tuple[ComparedRunInput, ...]) -> ComparisonReport:
        if len(runs) < MIN_RUNS:
            raise ValueError(f"At least {MIN_RUNS} runs are required")
        if len(runs) > MAX_RUNS:
            raise ValueError(f"At most {MAX_RUNS} runs are supported")

        summaries = tuple(
            ComparedRunSummary(
                run_id=run.run_id,
                label=run.label,
                strategy_name=run.strategy_name,
                dataset_name=run.dataset_name,
                experiment_name=run.experiment_name,
            )
            for run in runs
        )

        metric_rows = _build_metric_matrix(runs)
        strategy_rows = _build_strategy_rows(runs)
        dataset_rows = _build_dataset_rows(runs)
        execution_rows = _build_execution_rows(runs)
        param_diffs = _build_parameter_diffs(runs)

        return ComparisonReport(
            comparison_version=COMPARISON_VERSION,
            run_count=len(runs),
            runs=summaries,
            metric_rows=metric_rows,
            insights=build_insights(runs),
            strategy_rows=strategy_rows,
            strategy_parameter_diffs=param_diffs,
            dataset_rows=dataset_rows,
            execution_rows=execution_rows,
            equity_overlays=_build_equity_overlays(runs),
            drawdown_overlays=_build_drawdown_overlays(runs),
            monthly_returns_overlays=_build_monthly_overlays(runs),
            datasets_differ=any(row.differs_from_baseline for row in dataset_rows[1:]),
            strategies_differ=any(row.differs_from_baseline for row in strategy_rows[1:]),
        )


def compare(runs: tuple[ComparedRunInput, ...]) -> ComparisonReport:
    return RunComparison().compare(runs)


def _build_metric_matrix(runs: tuple[ComparedRunInput, ...]) -> tuple[MetricComparisonRow, ...]:
    """One row per catalog metric, values taken from each run's report."""
    values_by_run = [run.analytics.metric_values() for run in runs]
    lookup = [{metric.key: metric for metric in metrics} for metrics in values_by_run]

    rows: list[MetricComparisonRow] = []
    for definition in METRIC_DEFINITIONS:
        values: list[float | None] = []
        for index in range(len(runs)):
            metric = lookup[index].get(definition.key)
            values.append(None if metric is None else metric.value)

        best_index, worst_index, is_tie = _rank_values(values, definition.higher_is_better)
        spread, spread_pct = _spread(values, best_index, worst_index, definition.higher_is_better)

        rows.append(
            MetricComparisonRow(
                key=definition.key,
                label=definition.label,
                category=definition.category,
                format=definition.format,
                precision=definition.precision,
                description=definition.description,
                higher_is_better=definition.higher_is_better,
                values=tuple(values),
                best_run_index=best_index,
                worst_run_index=worst_index,
                is_tie=is_tie,
                spread=spread,
                spread_pct=spread_pct,
            )
        )
    return tuple(rows)


def _rank_values(
    values: list[float | None],
    higher_is_better: bool | None,
) -> tuple[int | None, int | None, bool]:
    """Return best index, worst index, and whether all ranked values tie."""
    if higher_is_better is None:
        return None, None, False

    ranked = [(index, value) for index, value in enumerate(values) if value is not None]
    if not ranked:
        return None, None, False

    if higher_is_better:
        best_index = max(ranked, key=lambda item: item[1])[0]
        worst_index = min(ranked, key=lambda item: item[1])[0]
    else:
        best_index = min(ranked, key=lambda item: item[1])[0]
        worst_index = max(ranked, key=lambda item: item[1])[0]

    numeric = [value for _, value in ranked]
    is_tie = len(set(numeric)) == 1
    if is_tie:
        return None, None, True
    return best_index, worst_index, False


def _spread(
    values: list[float | None],
    best_index: int | None,
    worst_index: int | None,
    higher_is_better: bool | None,
) -> tuple[float | None, float | None]:
    if higher_is_better is None or best_index is None or worst_index is None:
        return None, None

    best = values[best_index]
    worst = values[worst_index]
    if best is None or worst is None:
        return None, None

    if higher_is_better:
        spread = best - worst
        reference = abs(worst)
    else:
        spread = worst - best
        reference = abs(worst)

    if reference == 0:
        return spread, None
    return spread, (spread / reference) * 100.0


def _build_strategy_rows(runs: tuple[ComparedRunInput, ...]) -> tuple[StrategyComparisonRow, ...]:
    baseline = runs[0]
    rows: list[StrategyComparisonRow] = []
    for run in runs:
        differs = (
            run.strategy_id != baseline.strategy_id
            or run.strategy_hash != baseline.strategy_hash
            or run.library_strategy_id != baseline.library_strategy_id
            or run.library_strategy_version != baseline.library_strategy_version
        )
        rows.append(
            StrategyComparisonRow(
                run_id=run.run_id,
                run_label=run.label,
                strategy_id=run.strategy_id,
                strategy_name=run.strategy_name,
                strategy_hash=run.strategy_hash,
                library_strategy_id=run.library_strategy_id,
                library_strategy_version=run.library_strategy_version,
                strategy_params=run.strategy_params,
                differs_from_baseline=differs,
            )
        )
    return tuple(rows)


def _build_dataset_rows(runs: tuple[ComparedRunInput, ...]) -> tuple[DatasetComparisonRow, ...]:
    baseline = runs[0]
    rows: list[DatasetComparisonRow] = []
    for run in runs:
        differs = (
            run.dataset_id != baseline.dataset_id
            or run.dataset_hash != baseline.dataset_hash
            or run.dataset_version_number != baseline.dataset_version_number
        )
        rows.append(
            DatasetComparisonRow(
                run_id=run.run_id,
                run_label=run.label,
                dataset_id=run.dataset_id,
                dataset_name=run.dataset_name,
                dataset_version_number=run.dataset_version_number,
                dataset_hash=run.dataset_hash,
                dataset_imported_at=run.dataset_imported_at,
                dataset_quality_score=run.dataset_quality_score,
                differs_from_baseline=differs,
            )
        )
    return tuple(rows)


def _build_execution_rows(runs: tuple[ComparedRunInput, ...]) -> tuple[ExecutionComparisonRow, ...]:
    return tuple(
        ExecutionComparisonRow(
            run_id=run.run_id,
            run_label=run.label,
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
        )
        for run in runs
    )


def _build_parameter_diffs(runs: tuple[ComparedRunInput, ...]) -> tuple[StrategyParameterDiff, ...]:
    names: dict[str, None] = {}
    for run in runs:
        if run.strategy_params:
            for name in run.strategy_params:
                names.setdefault(name, None)

    diffs: list[StrategyParameterDiff] = []
    for name in sorted(names):
        values: list[Any] = []
        for run in runs:
            params = run.strategy_params or {}
            values.append(params.get(name))
        differs = len({repr(value) for value in values}) > 1
        diffs.append(StrategyParameterDiff(name=name, values=tuple(values), differs=differs))
    return tuple(diffs)


def _build_equity_overlays(runs: tuple[ComparedRunInput, ...]) -> tuple[EquityOverlay, ...]:
    return tuple(
        EquityOverlay(
            run_id=run.run_id,
            run_label=run.label,
            points=tuple(run.analytics.series.equity_curve),
        )
        for run in runs
    )


def _build_drawdown_overlays(runs: tuple[ComparedRunInput, ...]) -> tuple[DrawdownOverlay, ...]:
    return tuple(
        DrawdownOverlay(
            run_id=run.run_id,
            run_label=run.label,
            points=tuple(run.analytics.series.drawdown_curve),
            max_drawdown_start_ts=run.analytics.series.max_drawdown_start_ts,
            max_drawdown_trough_ts=run.analytics.series.max_drawdown_trough_ts,
            max_drawdown_recovery_ts=run.analytics.series.max_drawdown_recovery_ts,
        )
        for run in runs
    )


def _build_monthly_overlays(
    runs: tuple[ComparedRunInput, ...],
) -> tuple[MonthlyReturnsOverlay, ...]:
    return tuple(
        MonthlyReturnsOverlay(
            run_id=run.run_id,
            run_label=run.label,
            returns=tuple(run.analytics.series.monthly_returns),
        )
        for run in runs
    )


def metrics_for_category(
    rows: tuple[MetricComparisonRow, ...],
    category: MetricCategory,
) -> tuple[MetricComparisonRow, ...]:
    return tuple(row for row in rows if row.category == category)
