"""Documentation generation from strategy declarations."""

from __future__ import annotations

from app.engine.strategy.definition import build_definition
from app.engine.strategy.documentation import build_documentation, render_markdown
from app.engine.strategy.library.ema_crossover import EmaCrossoverStrategy
from app.engine.strategy.registry import StrategyRegistry


def test_build_documentation_includes_parameters_and_rules():
    definition = build_definition(EmaCrossoverStrategy)
    doc = build_documentation(definition)

    assert doc.strategy_id == "ema_crossover"
    assert doc.parameters
    assert doc.entry_rules
    assert doc.exit_rules
    assert doc.risk_rules
    assert doc.known_limitations


def test_render_markdown_contains_headings_and_parameter_table():
    definition = build_definition(EmaCrossoverStrategy)
    doc = build_documentation(definition)
    markdown = render_markdown(doc)

    assert markdown.startswith("# EMA Crossover")
    assert "## Overview" in markdown
    assert "## Parameters" in markdown
    assert "| Parameter |" in markdown
    assert "## Known limitations" in markdown


def test_every_discovered_strategy_generates_documentation():
    registry = StrategyRegistry()
    registry.discover()
    for definition in registry.all():
        doc = build_documentation(definition)
        markdown = render_markdown(doc)
        assert doc.strategy_id == definition.id
        assert doc.name
        assert markdown.strip()
