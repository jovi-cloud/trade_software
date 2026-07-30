"""Strategy declaration validation."""

from __future__ import annotations

from app.domain.enums import Timeframe
from app.engine.strategy.framework import StrategyBase
from app.engine.strategy.metadata import StrategyDocumentation, StrategyExample
from app.engine.strategy.validation import validate_registry, validate_strategy_class
from tests.unit.engine.strategy.conftest import make_metadata
from tests.unit.engine.strategy.test_params import spec


class _CompleteStrategy(StrategyBase):
    metadata = make_metadata()
    parameters = (spec(name="period"),)

    def entry_signal(self, view):
        return None

    def exit_signal(self, view):
        return None


def test_a_complete_declaration_passes_validation():
    report = validate_strategy_class(
        strategy_id="test_strategy",
        metadata=_CompleteStrategy.metadata,
        parameters=_CompleteStrategy.parameters,
        has_entry_rule=True,
        has_exit_rule=True,
    )
    assert report.is_valid
    assert not report.errors


def test_missing_metadata_is_an_error():
    report = validate_strategy_class(
        strategy_id="orphan",
        metadata=None,
        parameters=(),
        has_entry_rule=False,
        has_exit_rule=False,
    )
    assert not report.is_valid
    assert report.errors[0].code == "MISSING_METADATA"


def test_id_mismatch_is_an_error():
    metadata = make_metadata(id="declared_id")
    report = validate_strategy_class(
        strategy_id="registered_id",
        metadata=metadata,
        parameters=(),
        has_entry_rule=True,
        has_exit_rule=True,
    )
    assert any(finding.code == "ID_MISMATCH" for finding in report.errors)


def test_duplicate_parameter_names_are_rejected():
    report = validate_strategy_class(
        strategy_id="test_strategy",
        metadata=make_metadata(),
        parameters=(spec(name="period"), spec(name="period")),
        has_entry_rule=True,
        has_exit_rule=True,
    )
    assert any(finding.code == "DUPLICATE_PARAM" for finding in report.errors)


def test_an_example_with_bad_params_is_rejected():
    metadata = make_metadata(
        examples=(
            StrategyExample(
                title="Broken",
                description="Uses an out-of-range period.",
                instrument="TEST",
                timeframe=Timeframe.D1,
                params={"period": 1_000},
            ),
        ),
    )
    report = validate_strategy_class(
        strategy_id=metadata.id,
        metadata=metadata,
        parameters=(spec(name="period"),),
        has_entry_rule=True,
        has_exit_rule=True,
    )
    assert any(finding.code == "INVALID_EXAMPLE_PARAM" for finding in report.errors)


def test_missing_overview_is_an_error():
    metadata = make_metadata(
        documentation=StrategyDocumentation(overview=""),
    )
    report = validate_strategy_class(
        strategy_id=metadata.id,
        metadata=metadata,
        parameters=(),
        has_entry_rule=True,
        has_exit_rule=True,
    )
    assert any(finding.code == "MISSING_OVERVIEW" for finding in report.errors)


def test_validate_registry_detects_duplicate_names():
    one = make_metadata(id="one", name="Same Name")
    two = make_metadata(id="two", name="Same Name")
    findings = validate_registry({"one": one, "two": two})
    assert any(finding.code == "DUPLICATE_STRATEGY_NAME" for finding in findings)
