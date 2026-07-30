"""What a definition says about the explainability a run of it should collect.

The run workflow reads these two properties to pick a default, so getting them
wrong silently downgrades the Decision Inspector rather than failing loudly.
"""

from __future__ import annotations

from app.domain.explain import ExplainLevel
from app.engine.bars import Bar
from app.engine.strategy.definition import build_definition
from app.engine.strategy.framework import StrategyBase
from app.engine.strategy.registry import StrategyRegistry
from tests.unit.engine.strategy.conftest import make_metadata


class _FrameworkStrategy(StrategyBase):
    metadata = make_metadata(id="traced", name="Traced")


class _OptedOutStrategy(StrategyBase):
    """Replaces the hook that routes rules through ``check()``."""

    metadata = make_metadata(id="untraced", name="Untraced")

    def on_bar(self, bar: Bar) -> None:
        return None


def test_a_framework_strategy_traces_its_conditions():
    definition = build_definition(_FrameworkStrategy)
    assert definition.traces_conditions is True
    assert definition.recommended_explain_level is ExplainLevel.FULL


def test_replacing_on_bar_opts_out_of_condition_tracing():
    definition = build_definition(_OptedOutStrategy)
    assert definition.traces_conditions is False
    assert definition.recommended_explain_level is ExplainLevel.TRADES_ONLY


def test_every_shipped_strategy_recommends_full_explainability():
    registry = StrategyRegistry()
    registry.discover()
    assert [d.id for d in registry.all() if not d.traces_conditions] == []
