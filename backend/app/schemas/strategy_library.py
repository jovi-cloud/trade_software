"""Strategy Library DTOs.

Built from the engine's frozen dataclasses by the mappers at the bottom of this
module rather than by ``model_validate`` on the dataclass: the API shape is
deliberately allowed to differ from the engine's internal shape (derived fields
like ``label`` and ``unit``, flattened enum values), and doing the conversion
explicitly is what keeps a rename inside the engine from silently changing the
public contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import (
    MarketType,
    ParamType,
    RiskLevel,
    StrategyCategory,
    Timeframe,
    ValidationRuleKind,
    ValidationSeverity,
)
from app.domain.explain import ExplainLevel
from app.engine.strategy.definition import StrategyDefinition
from app.engine.strategy.documentation import StrategyDoc
from app.engine.strategy.metadata import StrategyMetadata
from app.engine.strategy.params import (
    ParamSpec,
    ParamValidationReport,
    ValidationRule,
)
from app.engine.strategy.validation import StrategyValidationReport, ValidationFinding

#: A parameter value as it crosses the API. Ordered so a bool never widens to int.
ParamValueRead = bool | int | float | str


class ParamChoiceRead(BaseModel):
    value: str
    label: str
    description: str = ""


class ValidationRuleRead(BaseModel):
    kind: ValidationRuleKind
    other_param: str | None = None
    value: float | None = None
    description: str = Field(description="Rendered rule text for the parameter editor")


class ParamSpecRead(BaseModel):
    """One parameter, with everything the generated editor needs to render it."""

    name: str
    label: str
    type: ParamType
    description: str
    default: ParamValueRead
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    choices: list[ParamChoiceRead] = Field(default_factory=list)
    group: str
    display_order: int
    tooltip: str = ""
    unit: str = Field(default="", description="Suffix shown after the input, e.g. %")
    rules: list[ValidationRuleRead] = Field(default_factory=list)


class ParamGroupRead(BaseModel):
    """Parameters bundled into one editor section."""

    name: str
    parameters: list[ParamSpecRead]


class ValidationFindingRead(BaseModel):
    code: str
    message: str
    severity: ValidationSeverity
    section: str
    param: str | None = None


class StrategyValidationRead(BaseModel):
    """Verdict on a strategy's own declaration."""

    is_valid: bool
    errors: list[ValidationFindingRead] = Field(default_factory=list)
    warnings: list[ValidationFindingRead] = Field(default_factory=list)


class ParamFindingRead(BaseModel):
    param: str | None = None
    code: str
    message: str
    severity: ValidationSeverity


class ParamValidationRead(BaseModel):
    """Verdict on a candidate parameter set, plus the values that would be used."""

    strategy_id: str
    is_valid: bool
    errors: list[ParamFindingRead] = Field(default_factory=list)
    warnings: list[ParamFindingRead] = Field(default_factory=list)
    resolved_params: dict[str, ParamValueRead] = Field(
        default_factory=dict,
        description="Values after coercion; rejected values fall back to their default",
    )


class ParamValidateRequest(BaseModel):
    params: dict[str, ParamValueRead] = Field(default_factory=dict)


class StrategyExampleRead(BaseModel):
    title: str
    description: str
    instrument: str
    timeframe: Timeframe
    params: dict[str, ParamValueRead] = Field(default_factory=dict)


class ChangelogEntryRead(BaseModel):
    version: str
    date: str
    changes: list[str]


class LibraryStrategyListItem(BaseModel):
    """Card-sized summary for the Strategy Library grid."""

    id: str
    name: str
    description: str
    version: str
    author: str
    category: StrategyCategory
    risk_level: RiskLevel
    markets: list[MarketType]
    timeframes: list[Timeframe]
    tags: list[str]
    direction: str
    styles: list[str]
    supports_long: bool
    supports_short: bool
    supports_intraday: bool
    supports_swing: bool
    supports_position_trading: bool
    parameter_count: int
    is_valid: bool
    error_count: int
    warning_count: int
    supports_condition_tracing: bool = Field(
        description="Whether a run of this strategy fills the Decision Inspector"
    )
    recommended_explain_level: ExplainLevel = Field(
        description="Explainability level the run workflow defaults to for this strategy"
    )


class LibraryStrategyRead(LibraryStrategyListItem):
    """Everything about one library strategy."""

    module: str
    overview: str
    parameters: list[ParamSpecRead]
    parameter_groups: list[ParamGroupRead]
    default_params: dict[str, ParamValueRead]
    examples: list[StrategyExampleRead]
    changelog: list[ChangelogEntryRead]
    validation: StrategyValidationRead


class ParameterSetRead(BaseModel):
    """The parameter contract for one strategy, grouped for the editor."""

    strategy_id: str
    version: str
    parameters: list[ParamSpecRead]
    groups: list[ParamGroupRead]
    defaults: dict[str, ParamValueRead]


class DocumentedParameterRead(BaseModel):
    name: str
    label: str
    type: str
    description: str
    default: str
    range: str
    group: str
    tooltip: str
    rules: list[str]


class DocumentedExampleRead(BaseModel):
    title: str
    description: str
    instrument: str
    timeframe: str
    params: dict[str, str]


class StrategyDocumentationRead(BaseModel):
    """Generated documentation (Part 8), plus a markdown rendering of the same."""

    strategy_id: str
    name: str
    version: str
    author: str
    overview: str
    description: str
    category: str
    risk_level: str
    markets: list[str]
    timeframes: list[str]
    tags: list[str]
    direction: str
    styles: list[str]
    indicators: list[str]
    entry_rules: list[str]
    exit_rules: list[str]
    risk_rules: list[str]
    parameters: list[DocumentedParameterRead]
    examples: list[DocumentedExampleRead]
    changelog: list[ChangelogEntryRead]
    known_limitations: list[str]
    references: list[str]
    markdown: str


class FacetCountRead(BaseModel):
    value: str
    count: int


class LoadFailureRead(BaseModel):
    module: str
    error: str


class LibraryFacetsRead(BaseModel):
    """Filter-rail counts for the Strategy Library."""

    total: int
    valid_count: int
    invalid_count: int
    categories: list[FacetCountRead]
    tags: list[FacetCountRead]
    markets: list[FacetCountRead]
    timeframes: list[FacetCountRead]
    risk_levels: list[FacetCountRead]
    styles: list[FacetCountRead]
    load_failures: list[LoadFailureRead]


# ---------------------------------------------------------------------------
# Mappers: engine dataclass -> DTO
# ---------------------------------------------------------------------------


def to_param_spec(spec: ParamSpec) -> ParamSpecRead:
    return ParamSpecRead(
        name=spec.name,
        label=spec.label,
        type=spec.type,
        description=spec.description,
        default=spec.default,
        minimum=spec.minimum,
        maximum=spec.maximum,
        step=spec.step,
        choices=[
            ParamChoiceRead(value=c.value, label=c.label, description=c.description)
            for c in spec.choices
        ],
        group=spec.group,
        display_order=spec.display_order,
        tooltip=spec.tooltip,
        unit=spec.unit,
        rules=[_to_rule(rule, spec.name) for rule in spec.rules],
    )


def to_param_groups(specs: tuple[ParamSpec, ...]) -> list[ParamGroupRead]:
    """Preserve the display order the definition already resolved."""
    groups: list[ParamGroupRead] = []
    index: dict[str, ParamGroupRead] = {}
    for spec in specs:
        group = index.get(spec.group)
        if group is None:
            group = ParamGroupRead(name=spec.group, parameters=[])
            index[spec.group] = group
            groups.append(group)
        group.parameters.append(to_param_spec(spec))
    return groups


def to_validation(report: StrategyValidationReport) -> StrategyValidationRead:
    return StrategyValidationRead(
        is_valid=report.is_valid,
        errors=[_to_finding(f) for f in report.errors],
        warnings=[_to_finding(f) for f in report.warnings],
    )


def to_param_validation(strategy_id: str, report: ParamValidationReport) -> ParamValidationRead:
    return ParamValidationRead(
        strategy_id=strategy_id,
        is_valid=report.is_valid,
        errors=[
            ParamFindingRead(param=f.param, code=f.code, message=f.message, severity=f.severity)
            for f in report.errors
        ],
        warnings=[
            ParamFindingRead(param=f.param, code=f.code, message=f.message, severity=f.severity)
            for f in report.warnings
        ],
        resolved_params=dict(report.values),
    )


def to_list_item(definition: StrategyDefinition) -> LibraryStrategyListItem:
    return LibraryStrategyListItem(**_summary_fields(definition))


def to_detail(definition: StrategyDefinition) -> LibraryStrategyRead:
    metadata = definition.metadata
    ordered = definition.sorted_parameters
    return LibraryStrategyRead(
        **_summary_fields(definition),
        module=definition.module,
        overview=metadata.documentation.overview,
        parameters=[to_param_spec(spec) for spec in ordered],
        parameter_groups=to_param_groups(ordered),
        default_params=dict(definition.default_params()),
        examples=[
            StrategyExampleRead(
                title=example.title,
                description=example.description,
                instrument=example.instrument,
                timeframe=example.timeframe,
                params=dict(example.params),
            )
            for example in metadata.examples
        ],
        changelog=[
            ChangelogEntryRead(version=entry.version, date=entry.date, changes=list(entry.changes))
            for entry in metadata.changelog
        ],
        validation=to_validation(definition.validation),
    )


def to_parameter_set(definition: StrategyDefinition) -> ParameterSetRead:
    ordered = definition.sorted_parameters
    return ParameterSetRead(
        strategy_id=definition.id,
        version=definition.metadata.version,
        parameters=[to_param_spec(spec) for spec in ordered],
        groups=to_param_groups(ordered),
        defaults=dict(definition.default_params()),
    )


def to_documentation(doc: StrategyDoc, markdown: str) -> StrategyDocumentationRead:
    return StrategyDocumentationRead(
        strategy_id=doc.strategy_id,
        name=doc.name,
        version=doc.version,
        author=doc.author,
        overview=doc.overview,
        description=doc.description,
        category=doc.category,
        risk_level=doc.risk_level,
        markets=list(doc.markets),
        timeframes=list(doc.timeframes),
        tags=list(doc.tags),
        direction=doc.direction,
        styles=list(doc.styles),
        indicators=list(doc.indicators),
        entry_rules=list(doc.entry_rules),
        exit_rules=list(doc.exit_rules),
        risk_rules=list(doc.risk_rules),
        parameters=[
            DocumentedParameterRead(
                name=p.name,
                label=p.label,
                type=p.type,
                description=p.description,
                default=p.default,
                range=p.range,
                group=p.group,
                tooltip=p.tooltip,
                rules=list(p.rules),
            )
            for p in doc.parameters
        ],
        examples=[
            DocumentedExampleRead(
                title=e.title,
                description=e.description,
                instrument=e.instrument,
                timeframe=e.timeframe,
                params=dict(e.params),
            )
            for e in doc.examples
        ],
        changelog=[
            ChangelogEntryRead(version=entry.version, date=entry.date, changes=list(entry.changes))
            for entry in doc.changelog
        ],
        known_limitations=list(doc.known_limitations),
        references=list(doc.references),
        markdown=markdown,
    )


def _summary_fields(definition: StrategyDefinition) -> dict[str, object]:
    metadata: StrategyMetadata = definition.metadata
    return {
        "id": metadata.id,
        "name": metadata.name,
        "description": metadata.description,
        "version": metadata.version,
        "author": metadata.author,
        "category": metadata.category,
        "risk_level": metadata.risk_level,
        "markets": list(metadata.markets),
        "timeframes": list(metadata.timeframes),
        "tags": list(metadata.tags),
        "direction": metadata.direction_label,
        "styles": list(metadata.styles),
        "supports_long": metadata.supports_long,
        "supports_short": metadata.supports_short,
        "supports_intraday": metadata.supports_intraday,
        "supports_swing": metadata.supports_swing,
        "supports_position_trading": metadata.supports_position_trading,
        "parameter_count": len(definition.parameters),
        "is_valid": definition.is_valid,
        "error_count": len(definition.validation.errors),
        "warning_count": len(definition.validation.warnings),
        "supports_condition_tracing": definition.traces_conditions,
        "recommended_explain_level": definition.recommended_explain_level,
    }


def _to_rule(rule: ValidationRule, param_name: str) -> ValidationRuleRead:
    return ValidationRuleRead(
        kind=rule.kind,
        other_param=rule.other_param,
        value=rule.value,
        description=rule.describe(param_name),
    )


def _to_finding(finding: ValidationFinding) -> ValidationFindingRead:
    return ValidationFindingRead(
        code=finding.code,
        message=finding.message,
        severity=finding.severity,
        section=finding.section,
        param=finding.param,
    )
