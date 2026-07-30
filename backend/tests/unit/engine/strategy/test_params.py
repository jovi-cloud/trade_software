"""The parameter system: declarations, coercion, bounds and cross-param rules."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from app.domain.enums import ParamType, ValidationRuleKind, ValidationSeverity
from app.engine.strategy.params import (
    ParamChoice,
    ParamFinding,
    ParamSpec,
    ParamValues,
    StrategyParameterError,
    ValidationRule,
    default_values,
    resolve_or_raise,
    resolve_params,
    validate_specs,
)


def spec(**overrides: object) -> ParamSpec:
    base: dict[str, object] = {
        "name": "period",
        "type": ParamType.INTEGER,
        "description": "A lookback.",
        "default": 14,
        "minimum": 2,
        "maximum": 100,
        "step": 1,
    }
    base.update(overrides)
    return ParamSpec(**base)  # type: ignore[arg-type]


def codes(findings: Iterable[ParamFinding]) -> set[str]:
    return {finding.code for finding in findings}


# -- derived display fields ------------------------------------------------


def test_label_is_derived_from_the_parameter_name():
    assert spec(name="fast_period").label == "Fast Period"
    assert spec(name="atr").label == "Atr"


@pytest.mark.parametrize(
    ("param_type", "expected"),
    [
        (ParamType.PERCENTAGE, "%"),
        (ParamType.TIME, "HH:MM"),
        (ParamType.INTEGER, ""),
        (ParamType.PRICE, ""),
    ],
)
def test_unit_reflects_the_declared_type(param_type: ParamType, expected: str) -> None:
    assert spec(type=param_type, default=1).unit == expected


# -- spec-list validation --------------------------------------------------


def test_a_well_formed_spec_list_has_no_findings():
    assert validate_specs([spec()]) == ()


def test_duplicate_parameter_names_are_an_error():
    assert "DUPLICATE_PARAM" in codes(validate_specs([spec(), spec()]))


def test_a_non_identifier_name_is_rejected():
    assert "INVALID_PARAM_NAME" in codes(validate_specs([spec(name="fast period")]))


def test_an_inverted_range_is_an_error():
    findings = validate_specs([spec(minimum=100, maximum=2, default=50)])
    assert "INVERTED_RANGE" in codes(findings)


def test_a_non_positive_step_is_an_error():
    assert "INVALID_STEP" in codes(validate_specs([spec(step=0)]))


def test_a_default_outside_the_declared_range_is_an_error():
    findings = validate_specs([spec(default=500)])
    assert "INVALID_DEFAULT" in codes(findings)


def test_a_default_of_the_wrong_type_is_an_error():
    findings = validate_specs([spec(default="fourteen")])
    assert "INVALID_DEFAULT" in codes(findings)


def test_a_choice_parameter_without_options_is_an_error():
    findings = validate_specs(
        [spec(type=ParamType.CHOICE, default="a", minimum=None, maximum=None, step=None)]
    )
    assert "MISSING_CHOICES" in codes(findings)


def test_duplicate_choice_values_are_an_error():
    findings = validate_specs(
        [
            spec(
                type=ParamType.CHOICE,
                default="a",
                minimum=None,
                maximum=None,
                step=None,
                choices=(ParamChoice("a", "A"), ParamChoice("a", "Also A")),
            )
        ]
    )
    assert "DUPLICATE_CHOICE" in codes(findings)


def test_a_missing_description_is_only_a_warning():
    findings = validate_specs([spec(description="  ")])
    warnings = [f for f in findings if f.severity is ValidationSeverity.WARNING]
    assert "MISSING_PARAM_DESCRIPTION" in {f.code for f in warnings}


def test_an_unbounded_numeric_parameter_is_a_warning_not_an_error():
    findings = validate_specs([spec(maximum=None)])
    assert "UNBOUNDED_PARAM" in codes(findings)
    assert all(f.severity is ValidationSeverity.WARNING for f in findings)


def test_bounds_on_a_non_numeric_parameter_are_a_warning():
    findings = validate_specs(
        [spec(type=ParamType.BOOLEAN, default=True, minimum=0, maximum=1, step=None)]
    )
    assert "BOUND_ON_NON_NUMERIC" in codes(findings)


def test_a_rule_targeting_an_unknown_parameter_is_an_error():
    findings = validate_specs(
        [
            spec(
                rules=(
                    ValidationRule(
                        kind=ValidationRuleKind.LESS_THAN_PARAM, other_param="nonexistent"
                    ),
                )
            )
        ]
    )
    assert "RULE_UNKNOWN_TARGET" in codes(findings)


def test_a_rule_targeting_itself_is_an_error():
    findings = validate_specs(
        [
            spec(
                rules=(
                    ValidationRule(kind=ValidationRuleKind.LESS_THAN_PARAM, other_param="period"),
                )
            )
        ]
    )
    assert "RULE_SELF_TARGET" in codes(findings)


def test_a_value_rule_without_a_value_is_an_error():
    findings = validate_specs([spec(rules=(ValidationRule(kind=ValidationRuleKind.MULTIPLE_OF),))])
    assert "RULE_MISSING_VALUE" in codes(findings)


# -- value resolution ------------------------------------------------------


def test_missing_values_fall_back_to_declared_defaults():
    report = resolve_params([spec()], {})
    assert report.is_valid
    assert report.values == {"period": 14}


def test_a_supplied_value_overrides_the_default():
    report = resolve_params([spec()], {"period": 20})
    assert report.values["period"] == 20


def test_an_unknown_parameter_is_a_warning_and_is_ignored():
    report = resolve_params([spec()], {"periodd": 20})
    assert report.is_valid
    assert codes(report.warnings) == {"UNKNOWN_PARAM"}
    assert "periodd" not in report.values


def test_an_unknown_parameter_close_to_a_real_one_suggests_it():
    report = resolve_params([spec(name="fast_period")], {"fast_perid": 5})
    assert "did you mean 'fast_period'" in report.warnings[0].message


def test_a_value_below_the_minimum_is_rejected_and_falls_back_to_the_default():
    report = resolve_params([spec()], {"period": 1})
    assert not report.is_valid
    assert codes(report.errors) == {"OUT_OF_RANGE"}
    # Still runnable: a caller that ignores the report gets a valid set.
    assert report.values["period"] == 14


def test_a_value_above_the_maximum_is_rejected():
    report = resolve_params([spec()], {"period": 1_000})
    assert codes(report.errors) == {"OUT_OF_RANGE"}


def test_a_value_off_the_step_grid_is_rejected():
    numeric = spec(minimum=0, maximum=10, step=0.5, type=ParamType.FLOAT, default=1.0)
    report = resolve_params([numeric], {"period": 1.3})
    assert codes(report.errors) == {"OUT_OF_RANGE"}


def test_a_value_on_the_step_grid_is_accepted_despite_float_representation():
    numeric = spec(type=ParamType.FLOAT, default=0.0, minimum=0.0, maximum=1.0, step=0.1)
    report = resolve_params([numeric], {"period": 0.3})
    assert report.is_valid, report.errors


def test_a_boolean_must_be_a_boolean():
    boolean = spec(type=ParamType.BOOLEAN, default=False, minimum=None, maximum=None, step=None)
    assert not resolve_params([boolean], {"period": 1}).is_valid
    assert resolve_params([boolean], {"period": True}).is_valid


def test_an_integer_rejects_a_boolean():
    # bool subclasses int, so accepting it would turn a checkbox into a period.
    report = resolve_params([spec()], {"period": True})
    assert codes(report.errors) == {"INVALID_TYPE"}


def test_an_integer_accepts_an_integral_float_from_json():
    report = resolve_params([spec()], {"period": 20.0})
    assert report.is_valid
    assert report.values["period"] == 20
    assert isinstance(report.values["period"], int)


def test_an_integer_rejects_a_fractional_float():
    assert not resolve_params([spec()], {"period": 20.5}).is_valid


def test_a_float_rejects_a_non_finite_value():
    numeric = spec(type=ParamType.FLOAT, default=1.0, minimum=0.0, maximum=10.0, step=None)
    assert not resolve_params([numeric], {"period": float("inf")}).is_valid
    assert not resolve_params([numeric], {"period": float("nan")}).is_valid


def test_a_choice_must_be_one_of_the_declared_options():
    choice = spec(
        type=ParamType.CHOICE,
        default="a",
        minimum=None,
        maximum=None,
        step=None,
        choices=(ParamChoice("a", "A"), ParamChoice("b", "B")),
    )
    assert resolve_params([choice], {"period": "b"}).is_valid
    report = resolve_params([choice], {"period": "c"})
    assert codes(report.errors) == {"INVALID_TYPE"}
    assert "a, b" in report.errors[0].message


@pytest.mark.parametrize("value", ["9:5", "09:05", "23:59", "00:00"])
def test_a_time_accepts_and_normalises_valid_times(value: str) -> None:
    time_spec = spec(type=ParamType.TIME, default="09:15", minimum=None, maximum=None, step=None)
    report = resolve_params([time_spec], {"period": value})
    assert report.is_valid
    assert len(str(report.values["period"])) == 5


@pytest.mark.parametrize("value", ["24:00", "09:60", "0915", "nine", "09:15:00", ""])
def test_a_time_rejects_malformed_or_out_of_range_values(value: str) -> None:
    time_spec = spec(type=ParamType.TIME, default="09:15", minimum=None, maximum=None, step=None)
    assert not resolve_params([time_spec], {"period": value}).is_valid


def test_a_string_rejects_a_number():
    text = spec(type=ParamType.STRING, default="x", minimum=None, maximum=None, step=None)
    assert not resolve_params([text], {"period": 5}).is_valid


def test_percentage_and_price_accept_plain_numbers():
    for param_type in (ParamType.PERCENTAGE, ParamType.PRICE):
        numeric = spec(type=param_type, default=1.0, minimum=0.0, maximum=100.0, step=None)
        assert resolve_params([numeric], {"period": 2.5}).is_valid


# -- cross-parameter rules -------------------------------------------------


def test_a_less_than_rule_is_enforced_across_parameters():
    fast = spec(
        name="fast",
        default=5,
        rules=(ValidationRule(kind=ValidationRuleKind.LESS_THAN_PARAM, other_param="slow"),),
    )
    slow = spec(name="slow", default=20)
    assert resolve_params([fast, slow], {"fast": 5, "slow": 20}).is_valid
    report = resolve_params([fast, slow], {"fast": 30, "slow": 20})
    assert codes(report.errors) == {"RULE_VIOLATED"}
    assert "less than slow" in report.errors[0].message


def test_a_greater_than_rule_is_enforced():
    high = spec(
        name="high",
        default=50,
        rules=(ValidationRule(kind=ValidationRuleKind.GREATER_THAN_PARAM, other_param="low"),),
    )
    low = spec(name="low", default=10)
    assert not resolve_params([high, low], {"high": 5, "low": 10}).is_valid


def test_a_not_equal_rule_is_enforced():
    left = spec(
        name="left",
        default=5,
        rules=(ValidationRule(kind=ValidationRuleKind.NOT_EQUAL_PARAM, other_param="right"),),
    )
    right = spec(name="right", default=9)
    assert not resolve_params([left, right], {"left": 7, "right": 7}).is_valid


def test_a_multiple_of_rule_is_enforced():
    numeric = spec(
        type=ParamType.INTEGER,
        default=10,
        minimum=0,
        maximum=100,
        step=None,
        rules=(ValidationRule(kind=ValidationRuleKind.MULTIPLE_OF, value=5),),
    )
    assert resolve_params([numeric], {"period": 25}).is_valid
    assert not resolve_params([numeric], {"period": 26}).is_valid


def test_length_rules_apply_to_strings():
    text = spec(
        type=ParamType.STRING,
        default="abc",
        minimum=None,
        maximum=None,
        step=None,
        rules=(
            ValidationRule(kind=ValidationRuleKind.MIN_LENGTH, value=2),
            ValidationRule(kind=ValidationRuleKind.MAX_LENGTH, value=4),
        ),
    )
    assert resolve_params([text], {"period": "abcd"}).is_valid
    assert not resolve_params([text], {"period": "a"}).is_valid
    assert not resolve_params([text], {"period": "abcde"}).is_valid


def test_rule_descriptions_can_be_overridden():
    rule = ValidationRule(
        kind=ValidationRuleKind.LESS_THAN_PARAM,
        other_param="slow",
        message="Fast must be quicker than slow",
    )
    assert rule.describe("fast") == "Fast must be quicker than slow"


# -- resolve_or_raise and ParamValues --------------------------------------


def test_resolve_or_raise_returns_param_values_when_valid():
    values = resolve_or_raise([spec()], {"period": 30})
    assert values.period == 30
    assert values["period"] == 30
    assert values.integer("period") == 30


def test_resolve_or_raise_reports_every_error_at_once():
    fast = spec(
        name="fast",
        default=5,
        rules=(ValidationRule(kind=ValidationRuleKind.LESS_THAN_PARAM, other_param="slow"),),
    )
    slow = spec(name="slow", default=20)
    with pytest.raises(StrategyParameterError) as excinfo:
        resolve_or_raise([fast, slow], {"fast": 1_000, "slow": 20})
    assert len(excinfo.value.report.errors) >= 1
    assert "Invalid strategy parameters" in excinfo.value.message


def test_param_values_are_read_only_during_a_run():
    values = ParamValues({"period": 14})
    with pytest.raises(AttributeError, match="read-only"):
        values.period = 20


def test_param_values_reports_an_unknown_parameter_by_name():
    values = ParamValues({"period": 14})
    with pytest.raises(AttributeError, match="no parameter named 'missing'"):
        _ = values.missing


def test_param_values_typed_accessors_reject_the_wrong_type():
    values = ParamValues({"period": 14, "flag": True, "label": "x", "rate": 1.5})
    assert values.flag("flag") is True
    assert values.text("label") == "x"
    assert values.number("rate") == pytest.approx(1.5)
    with pytest.raises(TypeError, match="not an integer"):
        values.integer("flag")
    with pytest.raises(TypeError, match="not numeric"):
        values.number("label")
    with pytest.raises(TypeError, match="not a boolean"):
        values.flag("period")
    with pytest.raises(TypeError, match="not a string"):
        values.text("period")


def test_param_values_supports_containment_and_length():
    values = ParamValues({"a": 1, "b": 2})
    assert "a" in values
    assert "z" not in values
    assert len(values) == 2
    assert values.as_dict() == {"a": 1, "b": 2}


def test_default_values_extracts_the_declared_defaults():
    assert default_values([spec(name="a", default=1), spec(name="b", default=2)]) == {
        "a": 1,
        "b": 2,
    }
