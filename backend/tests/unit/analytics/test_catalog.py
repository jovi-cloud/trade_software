"""The metric catalog must stay in step with the computed groups.

These are the tests that make "add a field, add a definition" safe, and that
guarantee Run Comparison and PDF export can iterate every metric with a label, a
format and a direction attached.
"""

from __future__ import annotations

from dataclasses import fields

from app.analytics.catalog import (
    HEADLINE_METRIC_KEYS,
    METRIC_DEFINITIONS,
    METRIC_DEFINITIONS_BY_KEY,
    MetricCategory,
    MetricFormat,
    definitions_for,
)
from app.analytics.metrics import analyse
from app.analytics.report import AnalyticsReport
from tests.unit.analytics.conftest import make_input, pnl_trade


def _report() -> AnalyticsReport:
    return analyse(
        make_input(
            trades=tuple(
                pnl_trade(
                    index + 1, 100.0 if index % 2 else -50.0, entry_day=index, exit_day=index + 1
                )
                for index in range(40)
            ),
            closes=[100] * 41,
        )
    )


def test_every_group_field_has_a_definition() -> None:
    """A metric without a definition would be invisible to every consumer."""
    report = _report()
    for category in MetricCategory:
        group = report.group(category)
        for field in fields(group):  # type: ignore[arg-type]
            assert field.name in METRIC_DEFINITIONS_BY_KEY, (
                f"{category.value}.{field.name} has no catalog definition"
            )
            assert METRIC_DEFINITIONS_BY_KEY[field.name].category is category


def test_every_definition_maps_to_a_real_field() -> None:
    """A definition without a field would render a permanently blank card."""
    report = _report()
    for definition in METRIC_DEFINITIONS:
        group = report.group(definition.category)
        assert hasattr(group, definition.key), (
            f"catalog defines {definition.key} but {definition.category.value} has no such field"
        )


def test_metric_keys_are_unique() -> None:
    keys = [definition.key for definition in METRIC_DEFINITIONS]

    assert len(keys) == len(set(keys))


def test_every_definition_is_displayable() -> None:
    for definition in METRIC_DEFINITIONS:
        assert definition.label.strip()
        assert definition.description.strip()
        assert isinstance(definition.format, MetricFormat)
        assert definition.precision >= 0


def test_metric_values_cover_the_whole_catalog_in_order() -> None:
    values = _report().metric_values()

    assert [value.key for value in values] == [definition.key for definition in METRIC_DEFINITIONS]


def test_metric_values_carry_display_metadata() -> None:
    sharpe = _report().metric("sharpe_ratio")

    assert sharpe is not None
    assert sharpe.label == "Sharpe Ratio"
    assert sharpe.category is MetricCategory.RISK_ADJUSTED
    assert sharpe.format is MetricFormat.RATIO
    assert sharpe.higher_is_better is True
    assert sharpe.description


def test_headline_metrics_exist_and_are_a_strict_subset() -> None:
    assert HEADLINE_METRIC_KEYS
    assert set(HEADLINE_METRIC_KEYS) < set(METRIC_DEFINITIONS_BY_KEY)
    # The Overview section needs at least one metric from each of the three
    # questions a researcher asks first: did it make money, how much risk, and
    # was there enough evidence.
    headline_categories = {METRIC_DEFINITIONS_BY_KEY[key].category for key in HEADLINE_METRIC_KEYS}
    assert MetricCategory.RETURNS in headline_categories
    assert MetricCategory.RISK in headline_categories
    assert MetricCategory.TRADES in headline_categories


def test_definitions_for_filters_by_category() -> None:
    risk = definitions_for(MetricCategory.RISK)

    assert risk
    assert all(definition.category is MetricCategory.RISK for definition in risk)
    assert sum(len(definitions_for(category)) for category in MetricCategory) == len(
        METRIC_DEFINITIONS
    )


def test_an_undefined_metric_reports_none_rather_than_zero() -> None:
    """The distinction the whole ``float | None`` contract exists to preserve."""
    flat = analyse(make_input(trades=(), closes=[100] * 10))
    values = {value.key: value.value for value in flat.metric_values()}

    assert values["sharpe_ratio"] is None
    assert values["profit_factor"] is None
    assert values["total_trades"] == 0.0
