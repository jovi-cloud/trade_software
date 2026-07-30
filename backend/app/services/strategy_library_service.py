"""Read-side use cases over the strategy registry.

Stateless and session-free: the strategy library is code, not rows, so there is
nothing to persist and nothing to transact. This service exists so the router
stays a thin translate-and-return layer and so the registry stays an engine
concern that the API never reaches into directly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.core.exceptions import NotFoundError
from app.engine.strategy.definition import StrategyDefinition
from app.engine.strategy.documentation import StrategyDoc, build_documentation, render_markdown
from app.engine.strategy.params import ParamValidationReport
from app.engine.strategy.registry import StrategyRegistry, get_registry


class StrategyLibraryService:
    """Discovery, documentation and parameter validation for library strategies."""

    def __init__(self, registry: StrategyRegistry | None = None) -> None:
        self.registry = registry or get_registry()

    # -- listing ----------------------------------------------------------

    def search(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        tags: Sequence[str] = (),
        market: str | None = None,
        timeframe: str | None = None,
        risk_level: str | None = None,
        style: str | None = None,
        valid_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[tuple[StrategyDefinition, ...], int]:
        """Filter, then page. Returns the page and the unpaged total."""
        matches = self.registry.search(
            query=q or "",
            category=category,
            tags=tags,
            market=market,
            timeframe=timeframe,
            risk_level=risk_level,
            style=style,
            valid_only=valid_only,
        )
        return matches[offset : offset + limit], len(matches)

    def get(self, strategy_id: str) -> StrategyDefinition:
        definition = self.registry.find(strategy_id)
        if definition is None:
            raise NotFoundError(f"Strategy '{strategy_id}' is not in the strategy library")
        return definition

    def facets(self) -> dict[str, object]:
        """Counts the Strategy Library UI needs to render its filter rail."""
        definitions = self.registry.all()
        markets: dict[str, int] = {}
        timeframes: dict[str, int] = {}
        risk_levels: dict[str, int] = {}
        styles: dict[str, int] = {}

        for definition in definitions:
            metadata = definition.metadata
            for market in metadata.markets:
                markets[market.value] = markets.get(market.value, 0) + 1
            for timeframe in metadata.timeframes:
                timeframes[timeframe.value] = timeframes.get(timeframe.value, 0) + 1
            risk_levels[metadata.risk_level.value] = (
                risk_levels.get(metadata.risk_level.value, 0) + 1
            )
            for style in metadata.styles:
                styles[style] = styles.get(style, 0) + 1

        return {
            "total": len(definitions),
            "valid_count": len(self.registry.valid()),
            "invalid_count": len(self.registry.invalid()),
            "categories": _counts(self.registry.categories()),
            "tags": _counts(self.registry.tags()),
            "markets": _counts(tuple(sorted(markets.items()))),
            "timeframes": _counts(tuple(sorted(timeframes.items()))),
            "risk_levels": _counts(tuple(sorted(risk_levels.items()))),
            "styles": _counts(tuple(sorted(styles.items()))),
            "load_failures": [
                {"module": failure.module, "error": failure.error}
                for failure in self.registry.failures
            ],
        }

    # -- documentation ----------------------------------------------------

    def documentation(self, strategy_id: str) -> StrategyDoc:
        return build_documentation(self.get(strategy_id))

    def documentation_markdown(self, strategy_id: str) -> str:
        return render_markdown(self.documentation(strategy_id))

    # -- validation -------------------------------------------------------

    def validate_params(
        self, strategy_id: str, params: Mapping[str, object] | None
    ) -> ParamValidationReport:
        """Check a candidate configuration. Never runs the strategy."""
        return self.get(strategy_id).validate_params(params)

    def default_params(self, strategy_id: str) -> dict[str, object]:
        return dict(self.get(strategy_id).default_params())


def _counts(pairs: tuple[tuple[str, int], ...]) -> list[dict[str, object]]:
    return [{"value": value, "count": count} for value, count in pairs]
