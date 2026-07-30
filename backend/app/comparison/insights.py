"""Research insights — observations from existing metrics only."""

from __future__ import annotations

from app.comparison.inputs import ComparedRunInput
from app.comparison.report import ResearchInsight

#: Headline metrics worth calling out automatically. Keys must exist in the catalog.
INSIGHT_METRIC_KEYS: tuple[str, ...] = (
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "cagr_pct",
    "max_drawdown_pct",
    "win_rate_pct",
    "annualised_volatility_pct",
    "profit_factor",
    "recovery_factor",
    "net_profit",
    "total_return_pct",
)


def build_insights(runs: tuple[ComparedRunInput, ...]) -> tuple[ResearchInsight, ...]:
    """Pick the best run for each insight metric and phrase a short observation."""
    if len(runs) < 2:
        return ()

    # Index metric key → list of (run_index, MetricValue-like fields)
    by_key: dict[str, list[tuple[int, ComparedRunInput, float]]] = {}
    for index, run in enumerate(runs):
        for metric in run.analytics.metric_values():
            if metric.value is None:
                continue
            by_key.setdefault(metric.key, []).append((index, run, float(metric.value)))

    insights: list[ResearchInsight] = []
    for key in INSIGHT_METRIC_KEYS:
        entries = by_key.get(key)
        if not entries:
            continue

        # Use catalog metadata from the first run's metric list.
        definition = next(
            (metric for metric in runs[0].analytics.metric_values() if metric.key == key),
            None,
        )
        if definition is None:
            continue

        higher = definition.higher_is_better
        if higher is None:
            continue

        if higher:
            best_index, best_run, best_value = max(entries, key=lambda item: item[2])
            qualifier = "highest"
        else:
            best_index, best_run, best_value = min(entries, key=lambda item: item[2])
            qualifier = "lowest"

        # Skip when every run ties.
        values = [value for _, _, value in entries]
        if len(set(values)) == 1:
            continue

        insights.append(
            ResearchInsight(
                metric_key=key,
                metric_label=definition.label,
                run_index=best_index,
                run_id=best_run.run_id,
                run_label=best_run.label,
                value=best_value,
                message=(
                    f"Run {best_run.label} has the {qualifier} {definition.label} "
                    f"({best_value:.{definition.precision}f})."
                ),
            )
        )

    return tuple(insights)
