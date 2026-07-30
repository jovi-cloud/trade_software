"""Typed parameter declarations and value resolution.

One ``ParamSpec`` list per strategy powers three things from a single source of
truth: the auto-generated parameter editor in the UI, request-time validation
before a run starts, and (later) an optimiser's search space. Declaring the
range and step here is what keeps parameter optimisation from becoming a
refactor (ARCHITECTURE.md 2.2).

Nothing in this module executes strategy code or touches the engine's
execution mathematics - it converts untrusted input into a validated value map
and reports what it rejected.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace

from app.domain.enums import ParamType, ValidationRuleKind, ValidationSeverity

# Everything a parameter is allowed to be. Deliberately JSON-native: params
# round-trip through the API and are persisted in run snapshots as JSON.
ParamValue = int | float | bool | str

_NUMERIC_TYPES: frozenset[ParamType] = frozenset(
    {ParamType.INTEGER, ParamType.FLOAT, ParamType.PERCENTAGE, ParamType.PRICE}
)
_TEXT_TYPES: frozenset[ParamType] = frozenset({ParamType.STRING, ParamType.CHOICE, ParamType.TIME})

# Floats arriving from JSON carry representation error (0.1 + 0.2), so step and
# multiple-of checks compare against a tolerance rather than an exact modulo.
_STEP_TOLERANCE = 1e-9


class StrategyParameterError(Exception):
    """Raised when parameter values cannot be resolved into a runnable set.

    Carries the full report so callers can surface every problem at once
    instead of the first one.
    """

    def __init__(self, message: str, report: ParamValidationReport) -> None:
        super().__init__(message)
        self.message = message
        self.report = report


@dataclass(frozen=True, slots=True)
class ParamChoice:
    """One selectable option for a ``CHOICE`` parameter."""

    value: str
    label: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class ValidationRule:
    """A declarative constraint, renderable as help text and checkable here."""

    kind: ValidationRuleKind
    #: Target parameter for cross-parameter rules (``LESS_THAN_PARAM`` etc.).
    other_param: str | None = None
    #: Scalar operand for value rules (``MULTIPLE_OF``, ``MIN_LENGTH`` etc.).
    value: float | None = None
    #: Overrides the generated description when the default reads poorly.
    message: str = ""

    def describe(self, param_name: str) -> str:
        if self.message:
            return self.message
        other = self.other_param or "another parameter"
        match self.kind:
            case ValidationRuleKind.LESS_THAN_PARAM:
                return f"{param_name} must be less than {other}"
            case ValidationRuleKind.GREATER_THAN_PARAM:
                return f"{param_name} must be greater than {other}"
            case ValidationRuleKind.NOT_EQUAL_PARAM:
                return f"{param_name} must differ from {other}"
            case ValidationRuleKind.MULTIPLE_OF:
                return f"{param_name} must be a multiple of {_format_number(self.value)}"
            case ValidationRuleKind.MIN_LENGTH:
                return f"{param_name} must be at least {_format_number(self.value)} characters"
            case ValidationRuleKind.MAX_LENGTH:
                return f"{param_name} must be at most {_format_number(self.value)} characters"


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """The full declaration of one strategy parameter.

    ``name`` is the stable key used in stored run configs; renaming it breaks
    reproducibility of existing runs, so treat it as immutable once shipped.
    """

    name: str
    type: ParamType
    description: str
    default: ParamValue
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    choices: tuple[ParamChoice, ...] = ()
    group: str = "General"
    display_order: int = 0
    tooltip: str = ""
    rules: tuple[ValidationRule, ...] = ()

    @property
    def label(self) -> str:
        """Human-facing field label derived from ``name`` (``fast_period`` -> ``Fast Period``)."""
        return " ".join(word.capitalize() for word in self.name.split("_"))

    @property
    def unit(self) -> str:
        """Suffix the editor shows after the input, if the type implies one."""
        match self.type:
            case ParamType.PERCENTAGE:
                return "%"
            case ParamType.TIME:
                return "HH:MM"
            case _:
                return ""


@dataclass(frozen=True, slots=True)
class ParamFinding:
    """One problem found while validating a spec list or a value map."""

    param: str | None
    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR


@dataclass(frozen=True, slots=True)
class ParamValidationReport:
    """Errors and warnings, plus the values that survived coercion."""

    findings: tuple[ParamFinding, ...] = ()
    values: Mapping[str, ParamValue] = field(default_factory=dict)

    @property
    def errors(self) -> tuple[ParamFinding, ...]:
        return tuple(f for f in self.findings if f.severity is ValidationSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ParamFinding, ...]:
        return tuple(f for f in self.findings if f.severity is ValidationSeverity.WARNING)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def with_values(self, values: Mapping[str, ParamValue]) -> ParamValidationReport:
        return replace(self, values=dict(values))


class ParamValues:
    """Attribute and item access over a resolved parameter map.

    Strategies read ``self.params.fast_period``; the mapping is frozen so a
    strategy cannot mutate its own configuration mid-run and break the
    determinism guarantee (ARCHITECTURE.md 9).
    """

    __slots__ = ("_values",)

    # Annotated so type checking resolves the slot rather than falling through
    # to __getattr__, which would type every internal read as a ParamValue.
    _values: dict[str, ParamValue]

    def __init__(self, values: Mapping[str, ParamValue]) -> None:
        object.__setattr__(self, "_values", dict(values))

    def __getattr__(self, name: str) -> ParamValue:
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(f"Strategy has no parameter named '{name}'") from None

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Strategy parameters are read-only during a run")

    def __getitem__(self, name: str) -> ParamValue:
        return self._values[name]

    def __contains__(self, name: str) -> bool:
        return name in self._values

    def __iter__(self) -> Iterable[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"ParamValues({self._values!r})"

    def as_dict(self) -> dict[str, ParamValue]:
        return dict(self._values)

    def integer(self, name: str) -> int:
        """Read a parameter that must already be an int, for mypy-strict callers."""
        value = self._values[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"Parameter '{name}' is not an integer")
        return value

    def number(self, name: str) -> float:
        value = self._values[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"Parameter '{name}' is not numeric")
        return float(value)

    def flag(self, name: str) -> bool:
        value = self._values[name]
        if not isinstance(value, bool):
            raise TypeError(f"Parameter '{name}' is not a boolean")
        return value

    def text(self, name: str) -> str:
        value = self._values[name]
        if not isinstance(value, str):
            raise TypeError(f"Parameter '{name}' is not a string")
        return value


# --------------------------------------------------------------------------
# Spec-list validation (Part 5: catch a badly declared strategy before it runs)
# --------------------------------------------------------------------------


def validate_specs(specs: Sequence[ParamSpec]) -> tuple[ParamFinding, ...]:
    """Check a strategy's own parameter declarations for internal consistency."""
    findings: list[ParamFinding] = []
    seen: set[str] = set()
    known = {spec.name for spec in specs}

    for spec in specs:
        findings.extend(_validate_spec_identity(spec, seen))
        findings.extend(_validate_spec_bounds(spec))
        findings.extend(_validate_spec_choices(spec))
        findings.extend(_validate_spec_default(spec))
        findings.extend(_validate_spec_rules(spec, known))

    return tuple(findings)


def _validate_spec_identity(spec: ParamSpec, seen: set[str]) -> list[ParamFinding]:
    findings: list[ParamFinding] = []
    if not spec.name or not spec.name.isidentifier():
        findings.append(
            ParamFinding(
                param=spec.name or None,
                code="INVALID_PARAM_NAME",
                message=f"Parameter name '{spec.name}' is not a valid Python identifier",
            )
        )
    if spec.name in seen:
        findings.append(
            ParamFinding(
                param=spec.name,
                code="DUPLICATE_PARAM",
                message=f"Parameter '{spec.name}' is declared more than once",
            )
        )
    seen.add(spec.name)
    if not spec.description.strip():
        findings.append(
            ParamFinding(
                param=spec.name,
                code="MISSING_PARAM_DESCRIPTION",
                message=f"Parameter '{spec.name}' has no description",
                severity=ValidationSeverity.WARNING,
            )
        )
    return findings


def _validate_spec_bounds(spec: ParamSpec) -> list[ParamFinding]:
    findings: list[ParamFinding] = []
    if spec.type not in _NUMERIC_TYPES:
        for attribute in ("minimum", "maximum", "step"):
            if getattr(spec, attribute) is not None:
                findings.append(
                    ParamFinding(
                        param=spec.name,
                        code="BOUND_ON_NON_NUMERIC",
                        message=(
                            f"Parameter '{spec.name}' is {spec.type.value} but declares "
                            f"{attribute}, which only applies to numeric parameters"
                        ),
                        severity=ValidationSeverity.WARNING,
                    )
                )
        return findings

    if spec.minimum is not None and spec.maximum is not None and spec.minimum > spec.maximum:
        findings.append(
            ParamFinding(
                param=spec.name,
                code="INVERTED_RANGE",
                message=(
                    f"Parameter '{spec.name}' has minimum {_format_number(spec.minimum)} "
                    f"above maximum {_format_number(spec.maximum)}"
                ),
            )
        )
    if spec.step is not None and spec.step <= 0:
        findings.append(
            ParamFinding(
                param=spec.name,
                code="INVALID_STEP",
                message=f"Parameter '{spec.name}' has a step of {_format_number(spec.step)}; "
                "step must be positive",
            )
        )
    if spec.minimum is None or spec.maximum is None:
        findings.append(
            ParamFinding(
                param=spec.name,
                code="UNBOUNDED_PARAM",
                message=(
                    f"Parameter '{spec.name}' has no "
                    f"{'minimum' if spec.minimum is None else 'maximum'}; the editor cannot "
                    "offer a slider and an optimiser has no search bound"
                ),
                severity=ValidationSeverity.WARNING,
            )
        )
    return findings


def _validate_spec_choices(spec: ParamSpec) -> list[ParamFinding]:
    findings: list[ParamFinding] = []
    if spec.type is ParamType.CHOICE:
        if not spec.choices:
            findings.append(
                ParamFinding(
                    param=spec.name,
                    code="MISSING_CHOICES",
                    message=f"Choice parameter '{spec.name}' declares no options",
                )
            )
        values = [choice.value for choice in spec.choices]
        duplicates = {value for value in values if values.count(value) > 1}
        for duplicate in sorted(duplicates):
            findings.append(
                ParamFinding(
                    param=spec.name,
                    code="DUPLICATE_CHOICE",
                    message=f"Parameter '{spec.name}' lists the option '{duplicate}' twice",
                )
            )
    elif spec.choices:
        findings.append(
            ParamFinding(
                param=spec.name,
                code="CHOICES_ON_NON_CHOICE",
                message=(
                    f"Parameter '{spec.name}' is {spec.type.value} but declares choices; "
                    "they will be ignored"
                ),
                severity=ValidationSeverity.WARNING,
            )
        )
    return findings


def _validate_spec_default(spec: ParamSpec) -> list[ParamFinding]:
    coerced, error = _coerce(spec, spec.default)
    if error is not None:
        return [
            ParamFinding(
                param=spec.name,
                code="INVALID_DEFAULT",
                message=f"Default for '{spec.name}' is invalid: {error}",
            )
        ]
    bound_error = _check_bounds(spec, coerced)
    if bound_error is not None:
        return [
            ParamFinding(
                param=spec.name,
                code="INVALID_DEFAULT",
                message=f"Default for '{spec.name}' is invalid: {bound_error}",
            )
        ]
    return []


def _validate_spec_rules(spec: ParamSpec, known: set[str]) -> list[ParamFinding]:
    findings: list[ParamFinding] = []
    for rule in spec.rules:
        needs_other = rule.kind in {
            ValidationRuleKind.LESS_THAN_PARAM,
            ValidationRuleKind.GREATER_THAN_PARAM,
            ValidationRuleKind.NOT_EQUAL_PARAM,
        }
        if needs_other:
            if rule.other_param is None:
                findings.append(
                    ParamFinding(
                        param=spec.name,
                        code="RULE_MISSING_TARGET",
                        message=(
                            f"Rule {rule.kind.value} on '{spec.name}' names no target parameter"
                        ),
                    )
                )
            elif rule.other_param not in known:
                findings.append(
                    ParamFinding(
                        param=spec.name,
                        code="RULE_UNKNOWN_TARGET",
                        message=(
                            f"Rule {rule.kind.value} on '{spec.name}' targets "
                            f"'{rule.other_param}', which is not a parameter of this strategy"
                        ),
                    )
                )
            if rule.other_param == spec.name:
                findings.append(
                    ParamFinding(
                        param=spec.name,
                        code="RULE_SELF_TARGET",
                        message=f"Rule {rule.kind.value} on '{spec.name}' targets itself",
                    )
                )
        elif rule.value is None:
            findings.append(
                ParamFinding(
                    param=spec.name,
                    code="RULE_MISSING_VALUE",
                    message=f"Rule {rule.kind.value} on '{spec.name}' needs a value",
                )
            )
    return findings


# --------------------------------------------------------------------------
# Value resolution (Part 5: validate what the trader typed)
# --------------------------------------------------------------------------


def resolve_params(
    specs: Sequence[ParamSpec], provided: Mapping[str, object] | None = None
) -> ParamValidationReport:
    """Merge ``provided`` over the declared defaults, coercing and validating.

    Every parameter always ends up in ``report.values`` - a rejected value
    falls back to its default so a caller that ignores the report still gets a
    runnable set. Missing keys are not an error: defaults exist precisely so a
    stored config from an older strategy version keeps working when a
    parameter is added.
    """
    supplied = dict(provided or {})
    findings: list[ParamFinding] = []
    values: dict[str, ParamValue] = {}
    known = {spec.name for spec in specs}

    for name in sorted(set(supplied) - known):
        findings.append(
            ParamFinding(
                param=name,
                code="UNKNOWN_PARAM",
                message=_unknown_param_message(name, known),
                severity=ValidationSeverity.WARNING,
            )
        )

    for spec in specs:
        if spec.name not in supplied:
            values[spec.name] = spec.default
            continue

        coerced, type_error = _coerce(spec, supplied[spec.name])
        if type_error is not None:
            findings.append(ParamFinding(param=spec.name, code="INVALID_TYPE", message=type_error))
            values[spec.name] = spec.default
            continue

        bound_error = _check_bounds(spec, coerced)
        if bound_error is not None:
            findings.append(ParamFinding(param=spec.name, code="OUT_OF_RANGE", message=bound_error))
            values[spec.name] = spec.default
            continue

        values[spec.name] = coerced

    findings.extend(_check_cross_param_rules(specs, values))
    return ParamValidationReport(findings=tuple(findings), values=values)


def resolve_or_raise(
    specs: Sequence[ParamSpec], provided: Mapping[str, object] | None = None
) -> ParamValues:
    """Resolve for execution: any error aborts rather than silently substituting."""
    report = resolve_params(specs, provided)
    if not report.is_valid:
        summary = "; ".join(finding.message for finding in report.errors)
        raise StrategyParameterError(f"Invalid strategy parameters: {summary}", report)
    return ParamValues(report.values)


def default_values(specs: Sequence[ParamSpec]) -> dict[str, ParamValue]:
    return {spec.name: spec.default for spec in specs}


def _unknown_param_message(name: str, known: set[str]) -> str:
    suggestion = _closest(name, known)
    hint = f"; did you mean '{suggestion}'?" if suggestion else ""
    return f"'{name}' is not a parameter of this strategy and was ignored{hint}"


def _closest(name: str, candidates: set[str]) -> str | None:
    """Cheap typo hint: the candidate sharing the longest common prefix."""
    best: str | None = None
    best_score = 0
    for candidate in sorted(candidates):
        score = len({*name} & {*candidate}) if name[:1] == candidate[:1] else 0
        if score > best_score:
            best, best_score = candidate, score
    return best if best_score >= max(2, len(name) // 2) else None


def _coerce(spec: ParamSpec, raw: object) -> tuple[ParamValue, str | None]:
    """Convert an untyped input into the declared type, or explain why not."""
    match spec.type:
        case ParamType.BOOLEAN:
            if isinstance(raw, bool):
                return raw, None
            return spec.default, f"'{spec.name}' must be true or false, got {_describe(raw)}"

        case ParamType.INTEGER:
            # bool is an int subclass; accepting it would silently turn a
            # checkbox value into a period length.
            if isinstance(raw, bool):
                return spec.default, f"'{spec.name}' must be a whole number, got a boolean"
            if isinstance(raw, int):
                return raw, None
            if isinstance(raw, float) and float(raw).is_integer():
                return int(raw), None
            return spec.default, f"'{spec.name}' must be a whole number, got {_describe(raw)}"

        case ParamType.FLOAT | ParamType.PERCENTAGE | ParamType.PRICE:
            if isinstance(raw, bool):
                return spec.default, f"'{spec.name}' must be a number, got a boolean"
            if isinstance(raw, (int, float)):
                if not math.isfinite(float(raw)):
                    return spec.default, f"'{spec.name}' must be a finite number"
                return float(raw), None
            return spec.default, f"'{spec.name}' must be a number, got {_describe(raw)}"

        case ParamType.CHOICE:
            if not isinstance(raw, str):
                return spec.default, f"'{spec.name}' must be one of its listed options"
            allowed = [choice.value for choice in spec.choices]
            if raw not in allowed:
                return spec.default, (
                    f"'{spec.name}' must be one of {', '.join(allowed) or '(none declared)'}, "
                    f"got '{raw}'"
                )
            return raw, None

        case ParamType.TIME:
            if not isinstance(raw, str):
                return spec.default, f"'{spec.name}' must be a HH:MM time string"
            normalised = _normalise_time(raw)
            if normalised is None:
                return spec.default, (
                    f"'{spec.name}' must be a 24-hour HH:MM time between 00:00 and 23:59, "
                    f"got '{raw}'"
                )
            return normalised, None

        case ParamType.STRING:
            if not isinstance(raw, str):
                return spec.default, f"'{spec.name}' must be text, got {_describe(raw)}"
            return raw, None


def _normalise_time(raw: str) -> str | None:
    parts = raw.strip().split(":")
    if len(parts) != 2:
        return None
    hours, minutes = parts
    if not (hours.isdigit() and minutes.isdigit()):
        return None
    hour, minute = int(hours), int(minutes)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def _check_bounds(spec: ParamSpec, value: ParamValue) -> str | None:
    for rule in spec.rules:
        message = _check_value_rule(spec, rule, value)
        if message is not None:
            return message

    if spec.type in _TEXT_TYPES or spec.type is ParamType.BOOLEAN:
        return None
    number = float(value) if isinstance(value, (int, float)) else 0.0

    if spec.minimum is not None and number < spec.minimum:
        return (
            f"'{spec.name}' must be at least {_format_number(spec.minimum)}, "
            f"got {_format_number(number)}"
        )
    if spec.maximum is not None and number > spec.maximum:
        return (
            f"'{spec.name}' must be at most {_format_number(spec.maximum)}, "
            f"got {_format_number(number)}"
        )
    if spec.step is not None and spec.step > 0:
        origin = spec.minimum if spec.minimum is not None else 0.0
        offset = number - origin
        remainder = math.remainder(offset, spec.step)
        if abs(remainder) > _STEP_TOLERANCE:
            return (
                f"'{spec.name}' must move in steps of {_format_number(spec.step)} "
                f"from {_format_number(origin)}, got {_format_number(number)}"
            )
    return None


def _check_value_rule(spec: ParamSpec, rule: ValidationRule, value: ParamValue) -> str | None:
    if rule.value is None:
        return None
    match rule.kind:
        case ValidationRuleKind.MULTIPLE_OF:
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            if is_number and (
                rule.value == 0 or abs(math.remainder(float(value), rule.value)) > _STEP_TOLERANCE
            ):
                return rule.describe(spec.name)
        case ValidationRuleKind.MIN_LENGTH:
            if isinstance(value, str) and len(value) < int(rule.value):
                return rule.describe(spec.name)
        case ValidationRuleKind.MAX_LENGTH:
            if isinstance(value, str) and len(value) > int(rule.value):
                return rule.describe(spec.name)
        case _:
            return None
    return None


def _check_cross_param_rules(
    specs: Sequence[ParamSpec], values: Mapping[str, ParamValue]
) -> list[ParamFinding]:
    findings: list[ParamFinding] = []
    for spec in specs:
        for rule in spec.rules:
            if rule.other_param is None or rule.other_param not in values:
                continue
            mine = values[spec.name]
            theirs = values[rule.other_param]
            if not _both_numeric(mine, theirs):
                continue
            left, right = float(mine), float(theirs)
            violated = (
                (rule.kind is ValidationRuleKind.LESS_THAN_PARAM and left >= right)
                or (rule.kind is ValidationRuleKind.GREATER_THAN_PARAM and left <= right)
                or (rule.kind is ValidationRuleKind.NOT_EQUAL_PARAM and left == right)
            )
            if violated:
                findings.append(
                    ParamFinding(
                        param=spec.name,
                        code="RULE_VIOLATED",
                        message=(
                            f"{rule.describe(spec.name)} "
                            f"({_format_number(left)} vs {_format_number(right)})"
                        ),
                    )
                )
    return findings


def _both_numeric(left: ParamValue, right: ParamValue) -> bool:
    return all(
        isinstance(value, (int, float)) and not isinstance(value, bool) for value in (left, right)
    )


def _describe(raw: object) -> str:
    return f"{type(raw).__name__} {raw!r}"


def _format_number(value: float | None) -> str:
    """Render bounds without trailing ``.0`` so messages read naturally."""
    if value is None:
        return "?"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"
