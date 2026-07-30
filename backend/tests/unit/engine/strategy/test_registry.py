"""Strategy registry: discovery, search, load and cross-strategy validation."""

from __future__ import annotations

import pytest

from app.engine.strategy.framework import StrategyBase
from app.engine.strategy.registry import StrategyRegistry, reset_registry
from tests.unit.engine.strategy.conftest import make_metadata


class _StubStrategy(StrategyBase):
    metadata = make_metadata(id="stub_one", name="Stub One")


def test_discover_loads_all_ten_reference_strategies():
    registry = StrategyRegistry()
    registry.discover()
    assert len(registry) == 10
    assert registry.failures == ()
    assert len(registry.valid()) == 10


def test_discover_skips_private_modules():
    registry = StrategyRegistry()
    registry.discover()
    assert all(not definition.id.startswith("_") for definition in registry.all())


def test_get_raises_for_an_unknown_id():
    registry = StrategyRegistry()
    registry.register(_StubStrategy)
    with pytest.raises(LookupError, match="No strategy registered"):
        registry.get("missing")


def test_register_replaces_an_earlier_registration_with_the_same_id():
    registry = StrategyRegistry()
    first = registry.register(_StubStrategy)
    second = registry.register(_StubStrategy)
    assert first.id == second.id == "stub_one"
    assert len(registry) == 1


def test_load_refuses_an_invalid_strategy():
    class Broken(StrategyBase):
        pass

    registry = StrategyRegistry()
    registry.register(Broken)
    with pytest.raises(ValueError, match="failed validation"):
        registry.load("broken")


def test_search_filters_by_query_category_and_tags():
    registry = StrategyRegistry()
    registry.discover()
    ema = registry.search(query="ema crossover")
    assert len(ema) == 1
    assert ema[0].id == "ema_crossover"

    trend = registry.search(category="trend_following")
    assert trend
    assert all(item.metadata.category.value == "trend_following" for item in trend)

    tagged = registry.search(tags=["crossover"])
    assert tagged
    assert all("crossover" in item.metadata.tags for item in tagged)


def test_categories_and_tags_return_counts():
    registry = StrategyRegistry()
    registry.discover()
    categories = dict(registry.categories())
    tags = dict(registry.tags())
    assert categories
    assert tags
    assert sum(categories.values()) == len(registry)


def test_validate_registry_flags_duplicate_display_names():
    registry = StrategyRegistry()
    registry.register(_StubStrategy)
    registry.register(
        type(
            "_DuplicateName",
            (StrategyBase,),
            {"metadata": make_metadata(id="duplicate_name", name="Stub One")},
        )
    )
    codes = {finding.code for finding in registry.cross_findings}
    assert "DUPLICATE_STRATEGY_NAME" in codes


def test_reset_registry_clears_the_process_wide_singleton():
    reset_registry()
    from app.engine.strategy.registry import get_registry

    first = get_registry()
    reset_registry()
    second = get_registry()
    assert first is not second
