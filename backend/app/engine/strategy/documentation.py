"""Generate strategy documentation from the declaration.

Documentation is derived, never hand-maintained. A strategy's metadata,
parameter specs and risk rules already say everything a docs page needs; writing
it out a second time in prose guarantees the two drift apart, and a stale
parameter range in the docs is worse than no docs.

Two outputs from one structure: :class:`StrategyDoc` for the API (the UI renders
it as sections) and :func:`render_markdown` for anywhere plain text is wanted.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import ParamType
from app.engine.strategy.definition import StrategyDefinition
from app.engine.strategy.params import ParamSpec, ParamValue


@dataclass(frozen=True, slots=True)
class DocumentedParameter:
    """One parameter as the docs page shows it."""

    name: str
    label: str
    type: str
    description: str
    default: str
    range: str
    group: str
    tooltip: str
    rules: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DocumentedExample:
    title: str
    description: str
    instrument: str
    timeframe: str
    params: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class DocumentedChangelogEntry:
    version: str
    date: str
    changes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StrategyDoc:
    """The full generated documentation for one strategy (Part 8)."""

    strategy_id: str
    name: str
    version: str
    author: str
    overview: str
    description: str
    category: str
    risk_level: str
    markets: tuple[str, ...]
    timeframes: tuple[str, ...]
    tags: tuple[str, ...]
    direction: str
    styles: tuple[str, ...]
    indicators: tuple[str, ...]
    entry_rules: tuple[str, ...]
    exit_rules: tuple[str, ...]
    risk_rules: tuple[str, ...]
    parameters: tuple[DocumentedParameter, ...]
    examples: tuple[DocumentedExample, ...]
    changelog: tuple[DocumentedChangelogEntry, ...]
    known_limitations: tuple[str, ...]
    references: tuple[str, ...]


def build_documentation(definition: StrategyDefinition) -> StrategyDoc:
    """Assemble the docs page for one strategy."""
    metadata = definition.metadata
    docs = metadata.documentation

    return StrategyDoc(
        strategy_id=metadata.id,
        name=metadata.name,
        version=metadata.version,
        author=metadata.author,
        overview=docs.overview,
        description=metadata.description,
        category=metadata.category.value,
        risk_level=metadata.risk_level.value,
        markets=tuple(market.value for market in metadata.markets),
        timeframes=tuple(timeframe.value for timeframe in metadata.timeframes),
        tags=metadata.tags,
        direction=metadata.direction_label,
        styles=metadata.styles,
        indicators=docs.indicators,
        entry_rules=docs.entry_rules,
        exit_rules=docs.exit_rules,
        risk_rules=_risk_rule_lines(definition, docs.risk_rules),
        parameters=tuple(_document_parameter(spec) for spec in definition.sorted_parameters),
        examples=tuple(
            DocumentedExample(
                title=example.title,
                description=example.description,
                instrument=example.instrument,
                timeframe=example.timeframe.value,
                params=tuple(
                    (name, _format_value(value)) for name, value in sorted(example.params.items())
                ),
            )
            for example in metadata.examples
        ),
        changelog=tuple(
            DocumentedChangelogEntry(version=entry.version, date=entry.date, changes=entry.changes)
            for entry in metadata.changelog
        ),
        known_limitations=docs.known_limitations,
        references=docs.references,
    )


def render_markdown(doc: StrategyDoc) -> str:
    """Render a generated doc as markdown."""
    lines: list[str] = [f"# {doc.name}", ""]
    lines.append(f"**Version:** {doc.version} · **Author:** {doc.author}")
    lines.append(
        f"**Category:** {_humanise(doc.category)} · **Risk level:** {_humanise(doc.risk_level)} "
        f"· **Direction:** {doc.direction}"
    )
    lines.extend(["", "## Overview", "", doc.overview or doc.description, ""])

    lines.extend(
        [
            "## Markets & timeframes",
            "",
            f"- **Markets:** {_join(doc.markets) or 'not declared'}",
            f"- **Timeframes:** {_join(doc.timeframes) or 'not declared'}",
            f"- **Styles:** {_join(doc.styles) or 'not declared'}",
            f"- **Tags:** {_join(doc.tags) or 'none'}",
            "",
        ]
    )

    _append_list(lines, "Indicators", doc.indicators)
    _append_list(lines, "Entry rules", doc.entry_rules)
    _append_list(lines, "Exit rules", doc.exit_rules)
    _append_list(lines, "Risk rules", doc.risk_rules)

    if doc.parameters:
        lines.extend(["## Parameters", ""])
        lines.append("| Parameter | Type | Default | Range | Description |")
        lines.append("| --- | --- | --- | --- | --- |")
        for param in doc.parameters:
            lines.append(
                f"| `{param.name}` | {param.type} | {param.default} | {param.range} "
                f"| {param.description} |"
            )
        lines.append("")

    if doc.examples:
        lines.extend(["## Examples", ""])
        for example in doc.examples:
            lines.append(f"### {example.title}")
            lines.append("")
            lines.append(example.description)
            lines.append("")
            lines.append(f"- **Instrument:** {example.instrument}")
            lines.append(f"- **Timeframe:** {example.timeframe}")
            if example.params:
                rendered = ", ".join(f"`{name}={value}`" for name, value in example.params)
                lines.append(f"- **Parameters:** {rendered}")
            lines.append("")

    _append_list(lines, "Known limitations", doc.known_limitations)
    _append_list(lines, "References", doc.references)

    if doc.changelog:
        lines.extend(["## Changelog", ""])
        for entry in doc.changelog:
            lines.append(f"### {entry.version} - {entry.date}")
            lines.append("")
            for change in entry.changes:
                lines.append(f"- {change}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _risk_rule_lines(definition: StrategyDefinition, declared: tuple[str, ...]) -> tuple[str, ...]:
    """Prose risk rules plus what the declared ``RiskRules`` actually do at defaults.

    Generated from the rule objects so the docs cannot claim a 2x ATR stop while
    the code uses 1.5x.
    """
    try:
        generated = definition.declared_risk().describe()
    except Exception:
        generated = ()
    combined: list[str] = list(declared)
    for line in generated:
        if line not in combined:
            combined.append(line)
    return tuple(combined)


def _document_parameter(spec: ParamSpec) -> DocumentedParameter:
    return DocumentedParameter(
        name=spec.name,
        label=spec.label,
        type=spec.type.value,
        description=spec.description,
        default=_format_value(spec.default),
        range=_format_range(spec),
        group=spec.group,
        tooltip=spec.tooltip,
        rules=tuple(rule.describe(spec.name) for rule in spec.rules),
    )


def _format_range(spec: ParamSpec) -> str:
    if spec.type is ParamType.CHOICE:
        return " | ".join(choice.value for choice in spec.choices) or "no options declared"
    if spec.type is ParamType.BOOLEAN:
        return "true | false"
    if spec.type is ParamType.TIME:
        return "00:00 to 23:59"
    if spec.minimum is None and spec.maximum is None:
        return "unbounded"
    low = "-inf" if spec.minimum is None else _format_number(spec.minimum)
    high = "inf" if spec.maximum is None else _format_number(spec.maximum)
    step = f" step {_format_number(spec.step)}" if spec.step is not None else ""
    return f"{low} to {high}{step}{spec.unit and ' ' + spec.unit}"


def _format_value(value: ParamValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return _format_number(value)
    return str(value)


def _format_number(value: float | None) -> str:
    if value is None:
        return "?"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _humanise(value: str) -> str:
    return value.replace("_", " ").capitalize()


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values)


def _append_list(lines: list[str], heading: str, items: tuple[str, ...]) -> None:
    if not items:
        return
    lines.extend([f"## {heading}", ""])
    lines.extend(f"- {item}" for item in items)
    lines.append("")
