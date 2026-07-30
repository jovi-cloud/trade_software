"""Strategy validation: is this declaration coherent, and are these values legal?

Two distinct jobs, deliberately in one module because they share a finding
shape:

* :func:`validate_strategy_class` audits a strategy *declaration* - metadata,
  parameter specs, documentation, changelog. It runs at registration time so a
  badly declared strategy is caught when the library loads, not when a trader
  clicks Run.
* :func:`validate_registry` catches collisions that only exist between
  strategies: duplicate ids, duplicate display names.

Findings are split into errors and warnings. An **error** means the strategy
cannot be trusted to run and the registry marks it invalid; a **warning** means
it runs but something a trader relies on is missing (no description, no
example, an unbounded parameter an optimiser cannot search). Both are shown
before execution, which is what Part 5 asks for.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.enums import ValidationSeverity
from app.engine.strategy.metadata import StrategyMetadata
from app.engine.strategy.params import (
    ParamFinding,
    ParamSpec,
    ParamValidationReport,
    resolve_params,
    validate_specs,
)

#: Metadata fields that must be non-empty for a strategy to be considered valid.
REQUIRED_TEXT_FIELDS: tuple[str, ...] = ("id", "name", "description", "version", "author")


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """One problem with a strategy declaration."""

    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    #: Which part of the declaration this concerns: metadata, parameters, docs.
    section: str = "metadata"
    #: Parameter name, when the finding is about a specific parameter.
    param: str | None = None


@dataclass(frozen=True, slots=True)
class StrategyValidationReport:
    """The verdict on one strategy declaration."""

    strategy_id: str
    findings: tuple[ValidationFinding, ...] = ()

    @property
    def errors(self) -> tuple[ValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity is ValidationSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity is ValidationSeverity.WARNING)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def merge(self, other: StrategyValidationReport) -> StrategyValidationReport:
        return StrategyValidationReport(
            strategy_id=self.strategy_id,
            findings=self.findings + other.findings,
        )


def validate_strategy_class(
    *,
    strategy_id: str,
    metadata: StrategyMetadata | None,
    parameters: Sequence[ParamSpec],
    has_entry_rule: bool,
    has_exit_rule: bool,
) -> StrategyValidationReport:
    """Audit one strategy declaration in isolation."""
    findings: list[ValidationFinding] = []

    if metadata is None:
        return StrategyValidationReport(
            strategy_id=strategy_id,
            findings=(
                ValidationFinding(
                    code="MISSING_METADATA",
                    message=(
                        f"Strategy '{strategy_id}' declares no metadata; "
                        "set a StrategyMetadata on the class"
                    ),
                ),
            ),
        )

    findings.extend(_validate_metadata(metadata, strategy_id=strategy_id))
    findings.extend(_validate_documentation(metadata))
    findings.extend(_validate_changelog(metadata))
    findings.extend(_validate_examples(metadata, parameters))
    findings.extend(_promote(validate_specs(parameters), section="parameters"))
    findings.extend(_validate_rules(has_entry_rule=has_entry_rule, has_exit_rule=has_exit_rule))

    return StrategyValidationReport(strategy_id=strategy_id, findings=tuple(findings))


def validate_registry(
    entries: Mapping[str, StrategyMetadata],
) -> tuple[ValidationFinding, ...]:
    """Catch cross-strategy collisions: duplicate ids and duplicate names."""
    findings: list[ValidationFinding] = []

    by_name: dict[str, list[str]] = {}
    for strategy_id, metadata in entries.items():
        by_name.setdefault(metadata.name.strip().lower(), []).append(strategy_id)

    for name, ids in sorted(by_name.items()):
        if len(ids) > 1:
            findings.append(
                ValidationFinding(
                    code="DUPLICATE_STRATEGY_NAME",
                    message=(
                        f"Display name '{name}' is used by more than one strategy "
                        f"({', '.join(sorted(ids))}); the library would show them identically"
                    ),
                )
            )
    return tuple(findings)


def validate_parameter_values(
    parameters: Sequence[ParamSpec], values: Mapping[str, object] | None
) -> ParamValidationReport:
    """Validate trader-supplied values against the declared specs."""
    return resolve_params(parameters, values)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _validate_metadata(metadata: StrategyMetadata, *, strategy_id: str) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    for field_name in REQUIRED_TEXT_FIELDS:
        value = getattr(metadata, field_name)
        if not isinstance(value, str) or not value.strip():
            findings.append(
                ValidationFinding(
                    code="MISSING_REQUIRED_FIELD",
                    message=f"Metadata field '{field_name}' is required and must not be blank",
                )
            )

    if metadata.id != strategy_id:
        findings.append(
            ValidationFinding(
                code="ID_MISMATCH",
                message=(
                    f"Metadata id '{metadata.id}' does not match the registered id '{strategy_id}'"
                ),
            )
        )
    if metadata.id and not _is_slug(metadata.id):
        findings.append(
            ValidationFinding(
                code="INVALID_ID",
                message=(
                    f"Strategy id '{metadata.id}' must be lowercase letters, digits and "
                    "underscores - it appears in URLs and stored run configs"
                ),
            )
        )
    if not _is_semver(metadata.version):
        findings.append(
            ValidationFinding(
                code="INVALID_VERSION",
                message=(
                    f"Version '{metadata.version}' is not MAJOR.MINOR.PATCH; "
                    "comparing strategy versions across runs depends on it"
                ),
            )
        )
    if not metadata.markets:
        findings.append(
            ValidationFinding(
                code="NO_MARKETS",
                message="Declare at least one market this strategy is intended for",
            )
        )
    if not metadata.timeframes:
        findings.append(
            ValidationFinding(
                code="NO_TIMEFRAMES",
                message="Declare at least one timeframe this strategy is intended for",
            )
        )
    if not (metadata.supports_long or metadata.supports_short):
        findings.append(
            ValidationFinding(
                code="NO_DIRECTION",
                message="A strategy must support long, short, or both - this supports neither",
            )
        )
    if not metadata.styles:
        findings.append(
            ValidationFinding(
                code="NO_TRADING_STYLE",
                message=(
                    "Declare at least one of intraday, swing or position trading so the "
                    "library can filter by horizon"
                ),
                severity=ValidationSeverity.WARNING,
            )
        )
    if not metadata.tags:
        findings.append(
            ValidationFinding(
                code="NO_TAGS",
                message="No tags declared; the strategy will be hard to find by theme",
                severity=ValidationSeverity.WARNING,
            )
        )
    if metadata.supports_intraday and not metadata.supports_swing:
        intraday_only = all(
            timeframe.value.endswith("m") or timeframe.value.endswith("h")
            for timeframe in metadata.timeframes
        )
        if metadata.timeframes and not intraday_only:
            findings.append(
                ValidationFinding(
                    code="TIMEFRAME_STYLE_MISMATCH",
                    message=(
                        "Declared intraday-only but lists a daily or weekly timeframe; "
                        "one of the two is wrong"
                    ),
                    severity=ValidationSeverity.WARNING,
                )
            )
    return findings


def _validate_documentation(metadata: StrategyMetadata) -> list[ValidationFinding]:
    docs = metadata.documentation
    findings: list[ValidationFinding] = []

    if not docs.overview.strip():
        findings.append(
            ValidationFinding(
                code="MISSING_OVERVIEW",
                message="Documentation needs an overview explaining what the strategy does",
                section="documentation",
            )
        )
    if not docs.entry_rules:
        findings.append(
            ValidationFinding(
                code="MISSING_ENTRY_DOCS",
                message="Documentation lists no entry rules",
                severity=ValidationSeverity.WARNING,
                section="documentation",
            )
        )
    if not docs.exit_rules:
        findings.append(
            ValidationFinding(
                code="MISSING_EXIT_DOCS",
                message="Documentation lists no exit rules",
                severity=ValidationSeverity.WARNING,
                section="documentation",
            )
        )
    if not docs.known_limitations:
        findings.append(
            ValidationFinding(
                code="MISSING_LIMITATIONS",
                message=(
                    "No known limitations documented; every strategy has conditions where "
                    "it fails and hiding them costs the trader money"
                ),
                severity=ValidationSeverity.WARNING,
                section="documentation",
            )
        )
    return findings


def _validate_changelog(metadata: StrategyMetadata) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if not metadata.changelog:
        return [
            ValidationFinding(
                code="MISSING_CHANGELOG",
                message="No changelog; there is no record of how this strategy evolved",
                severity=ValidationSeverity.WARNING,
                section="changelog",
            )
        ]

    head = metadata.changelog[0]
    if head.version != metadata.version:
        findings.append(
            ValidationFinding(
                code="CHANGELOG_VERSION_MISMATCH",
                message=(
                    f"Newest changelog entry is {head.version} but the strategy declares "
                    f"version {metadata.version}"
                ),
                section="changelog",
            )
        )

    versions = [entry.version for entry in metadata.changelog]
    duplicates = {version for version in versions if versions.count(version) > 1}
    for duplicate in sorted(duplicates):
        findings.append(
            ValidationFinding(
                code="DUPLICATE_CHANGELOG_VERSION",
                message=f"Changelog lists version {duplicate} more than once",
                section="changelog",
            )
        )
    for entry in metadata.changelog:
        if not entry.changes:
            findings.append(
                ValidationFinding(
                    code="EMPTY_CHANGELOG_ENTRY",
                    message=f"Changelog entry {entry.version} lists no changes",
                    severity=ValidationSeverity.WARNING,
                    section="changelog",
                )
            )
    return findings


def _validate_examples(
    metadata: StrategyMetadata, parameters: Sequence[ParamSpec]
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if not metadata.examples:
        return [
            ValidationFinding(
                code="MISSING_EXAMPLE",
                message="No example configuration; a trader has no known-good starting point",
                severity=ValidationSeverity.WARNING,
                section="examples",
            )
        ]

    for example in metadata.examples:
        report = resolve_params(parameters, example.params)
        for error in report.errors:
            findings.append(
                ValidationFinding(
                    code="INVALID_EXAMPLE_PARAM",
                    message=f"Example '{example.title}': {error.message}",
                    section="examples",
                    param=error.param,
                )
            )
        if not metadata.supports_timeframe(example.timeframe.value):
            findings.append(
                ValidationFinding(
                    code="EXAMPLE_TIMEFRAME_UNSUPPORTED",
                    message=(
                        f"Example '{example.title}' uses {example.timeframe.value}, which is "
                        "not in the strategy's declared timeframes"
                    ),
                    severity=ValidationSeverity.WARNING,
                    section="examples",
                )
            )
    return findings


def _validate_rules(*, has_entry_rule: bool, has_exit_rule: bool) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if not has_entry_rule:
        findings.append(
            ValidationFinding(
                code="NO_ENTRY_RULE",
                message=("Strategy overrides no entry_signal; it can never open a position"),
                section="rules",
            )
        )
    if not has_exit_rule:
        findings.append(
            ValidationFinding(
                code="NO_EXIT_RULE",
                message=(
                    "Strategy overrides no exit_signal; it relies entirely on its risk rules "
                    "to close positions - make sure at least one is declared"
                ),
                severity=ValidationSeverity.WARNING,
                section="rules",
            )
        )
    return findings


def _promote(findings: Sequence[ParamFinding], *, section: str) -> list[ValidationFinding]:
    """Lift parameter findings into the strategy-level finding shape."""
    return [
        ValidationFinding(
            code=finding.code,
            message=finding.message,
            severity=finding.severity,
            section=section,
            param=finding.param,
        )
        for finding in findings
    ]


def _is_slug(value: str) -> bool:
    return bool(value) and all(char.islower() or char.isdigit() or char == "_" for char in value)


def _is_semver(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 3 and all(part.isdigit() for part in parts)
