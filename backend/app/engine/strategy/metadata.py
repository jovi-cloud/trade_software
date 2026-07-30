"""What a strategy declares about itself.

Metadata is not decoration: the Strategy Library's search, category and tag
facets, the generated documentation page, and the "can this strategy even trade
this instrument" checks all read from here. A strategy with weak metadata is a
strategy nobody can find, which is why ``validation.py`` treats gaps as
findings rather than ignoring them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.domain.enums import MarketType, RiskLevel, StrategyCategory, Timeframe
from app.engine.strategy.params import ParamValue


@dataclass(frozen=True, slots=True)
class ChangelogEntry:
    """One released version of a strategy and what changed in it.

    Newest first by convention; ``validation.py`` checks that the head entry
    matches ``StrategyMetadata.version``.
    """

    version: str
    date: str
    changes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StrategyExample:
    """A concrete, known-good configuration a trader can load in one click."""

    title: str
    description: str
    instrument: str
    timeframe: Timeframe
    params: Mapping[str, ParamValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StrategyDocumentation:
    """Prose and rule lists the documentation generator renders.

    Split by rule kind rather than stored as one markdown blob so the UI can
    show entry, exit and risk rules as separate, scannable sections - and so
    Part 1's "a strategy contains only indicators, conditions, entry, exit and
    risk rules" is visible in the declaration itself.
    """

    overview: str
    indicators: tuple[str, ...] = ()
    entry_rules: tuple[str, ...] = ()
    exit_rules: tuple[str, ...] = ()
    risk_rules: tuple[str, ...] = ()
    known_limitations: tuple[str, ...] = ()
    references: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    """Everything a strategy declares about itself (Part 2).

    ``id`` is the stable slug that stored run configurations reference. Once a
    strategy has shipped, changing its ``id`` orphans every saved reference to
    it - bump ``version`` instead.
    """

    id: str
    name: str
    description: str
    version: str
    author: str
    category: StrategyCategory
    markets: tuple[MarketType, ...]
    timeframes: tuple[Timeframe, ...]
    tags: tuple[str, ...]
    risk_level: RiskLevel
    supports_long: bool
    supports_short: bool
    supports_intraday: bool
    supports_swing: bool
    supports_position_trading: bool
    documentation: StrategyDocumentation
    examples: tuple[StrategyExample, ...] = ()
    changelog: tuple[ChangelogEntry, ...] = ()

    @property
    def direction_label(self) -> str:
        if self.supports_long and self.supports_short:
            return "Long & short"
        if self.supports_long:
            return "Long only"
        if self.supports_short:
            return "Short only"
        return "No direction declared"

    @property
    def styles(self) -> tuple[str, ...]:
        """Trading horizons this strategy declares support for."""
        declared = (
            ("intraday", self.supports_intraday),
            ("swing", self.supports_swing),
            ("position", self.supports_position_trading),
        )
        return tuple(name for name, supported in declared if supported)

    def supports_timeframe(self, timeframe: str) -> bool:
        return any(declared.value == timeframe for declared in self.timeframes)

    def supports_market(self, market: str) -> bool:
        return any(declared.value == market for declared in self.markets)

    def matches(self, query: str) -> bool:
        """Free-text search over the fields a trader would actually type."""
        needle = query.strip().lower()
        if not needle:
            return True
        haystack = " ".join(
            (
                self.id,
                self.name,
                self.description,
                self.author,
                self.category.value.replace("_", " "),
                *self.tags,
                self.documentation.overview,
            )
        ).lower()
        return needle in haystack
