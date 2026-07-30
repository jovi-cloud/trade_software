"""The strategy registry: register, discover, validate, load, list, cache.

## Discovery, and why it is dynamic

``discover()`` walks ``app.engine.strategy.library``, imports each module, and
registers every ``StrategyBase`` subclass it finds. Adding a strategy is
therefore exactly one new file - no registration list to edit, no engine module
to touch, which is the requirement the framework exists to satisfy.

## Caching

Discovery imports modules and audits every declaration, so the result is cached
on the registry instance and the process-wide default registry is built once.
``reset()`` exists for tests; nothing in production re-scans.

## Failure isolation

One strategy module that raises on import must not empty the library. Import
failures are captured as :class:`LoadFailure` entries and reported alongside the
strategies that did load, so the UI can show "9 strategies, 1 failed to load"
instead of silently showing nine.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.engine.strategy.definition import StrategyDefinition, build_definition
from app.engine.strategy.framework import StrategyBase
from app.engine.strategy.validation import ValidationFinding, validate_registry

#: Package scanned by :meth:`StrategyRegistry.discover`.
LIBRARY_PACKAGE = "app.engine.strategy.library"


class StrategyNotFoundError(LookupError):
    """Raised when a strategy id is not in the registry."""


@dataclass(frozen=True, slots=True)
class LoadFailure:
    """A library module that could not be imported."""

    module: str
    error: str


class StrategyRegistry:
    """An ordered, validated collection of strategy definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, StrategyDefinition] = {}
        self._failures: list[LoadFailure] = []
        self._cross_findings: tuple[ValidationFinding, ...] = ()
        self._discovered = False

    # -- registration -----------------------------------------------------

    def register(self, strategy_class: type[StrategyBase]) -> StrategyDefinition:
        """Audit and add one strategy class. Later registrations replace earlier ones."""
        definition = build_definition(strategy_class)
        self._definitions[definition.id] = definition
        self._recompute_cross_findings()
        return definition

    def register_all(self, strategy_classes: Iterable[type[StrategyBase]]) -> None:
        for strategy_class in strategy_classes:
            self.register(strategy_class)

    def discover(self, package: str = LIBRARY_PACKAGE) -> None:
        """Import every module in ``package`` and register the strategies found."""
        try:
            root = importlib.import_module(package)
        except ImportError as exc:
            self._failures.append(LoadFailure(module=package, error=str(exc)))
            self._discovered = True
            return

        search_paths = list(getattr(root, "__path__", ()))
        for module_info in sorted(pkgutil.iter_modules(search_paths), key=lambda info: info.name):
            if module_info.name.startswith("_"):
                continue
            module_name = f"{package}.{module_info.name}"
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                self._failures.append(
                    LoadFailure(module=module_name, error=f"{type(exc).__name__}: {exc}")
                )
                continue
            self.register_all(_strategy_classes_in(module))

        self._discovered = True

    # -- reading ----------------------------------------------------------

    @property
    def is_discovered(self) -> bool:
        return self._discovered

    @property
    def failures(self) -> tuple[LoadFailure, ...]:
        return tuple(self._failures)

    @property
    def cross_findings(self) -> tuple[ValidationFinding, ...]:
        """Findings that concern the collection rather than one strategy."""
        return self._cross_findings

    def __len__(self) -> int:
        return len(self._definitions)

    def __contains__(self, strategy_id: str) -> bool:
        return strategy_id in self._definitions

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))

    def all(self) -> tuple[StrategyDefinition, ...]:
        """Every definition, sorted by display name for stable listing."""
        return tuple(
            sorted(self._definitions.values(), key=lambda item: item.metadata.name.lower())
        )

    def get(self, strategy_id: str) -> StrategyDefinition:
        try:
            return self._definitions[strategy_id]
        except KeyError:
            raise StrategyNotFoundError(f"No strategy registered with id '{strategy_id}'") from None

    def find(self, strategy_id: str) -> StrategyDefinition | None:
        return self._definitions.get(strategy_id)

    def valid(self) -> tuple[StrategyDefinition, ...]:
        return tuple(item for item in self.all() if item.is_valid)

    def invalid(self) -> tuple[StrategyDefinition, ...]:
        return tuple(item for item in self.all() if not item.is_valid)

    def load(self, strategy_id: str, params: object | None = None) -> StrategyBase:
        """Instantiate a registered strategy, refusing to run an invalid one.

        Running a strategy whose declaration failed validation would produce
        results nobody can interpret - the parameter bounds an optimiser or the
        UI relied on are the very thing that failed to check out.
        """
        definition = self.get(strategy_id)
        if not definition.is_valid:
            reasons = "; ".join(finding.message for finding in definition.validation.errors)
            raise ValueError(f"Strategy '{strategy_id}' failed validation: {reasons}")
        mapping = params if isinstance(params, dict) else None
        return definition.instantiate(mapping)

    # -- facets for the library UI ----------------------------------------

    def categories(self) -> tuple[tuple[str, int], ...]:
        """Category values with strategy counts, most populated first."""
        counts: dict[str, int] = {}
        for definition in self._definitions.values():
            key = definition.metadata.category.value
            counts[key] = counts.get(key, 0) + 1
        return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def tags(self) -> tuple[tuple[str, int], ...]:
        counts: dict[str, int] = {}
        for definition in self._definitions.values():
            for tag in definition.metadata.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def search(
        self,
        *,
        query: str = "",
        category: str | None = None,
        tags: Sequence[str] = (),
        market: str | None = None,
        timeframe: str | None = None,
        risk_level: str | None = None,
        style: str | None = None,
        valid_only: bool = False,
    ) -> tuple[StrategyDefinition, ...]:
        """Filter the library. Every criterion is AND-ed; tags are AND-ed too."""
        results: list[StrategyDefinition] = []
        for definition in self.all():
            metadata = definition.metadata
            if valid_only and not definition.is_valid:
                continue
            if query and not metadata.matches(query):
                continue
            if category is not None and metadata.category.value != category:
                continue
            if tags and not set(tags).issubset(set(metadata.tags)):
                continue
            if market is not None and not metadata.supports_market(market):
                continue
            if timeframe is not None and not metadata.supports_timeframe(timeframe):
                continue
            if risk_level is not None and metadata.risk_level.value != risk_level:
                continue
            if style is not None and style not in metadata.styles:
                continue
            results.append(definition)
        return tuple(results)

    # -- maintenance ------------------------------------------------------

    def reset(self) -> None:
        self._definitions.clear()
        self._failures.clear()
        self._cross_findings = ()
        self._discovered = False

    def _recompute_cross_findings(self) -> None:
        self._cross_findings = validate_registry(
            {definition.id: definition.metadata for definition in self._definitions.values()}
        )


_default_registry: StrategyRegistry | None = None


def get_registry() -> StrategyRegistry:
    """The process-wide registry, discovered on first use.

    Module-level rather than injected because the contents are immutable code,
    not state: the same source tree always yields the same library. Callers that
    need isolation construct their own ``StrategyRegistry``.
    """
    global _default_registry
    if _default_registry is None:
        registry = StrategyRegistry()
        registry.discover()
        _default_registry = registry
    return _default_registry


def reset_registry() -> None:
    """Drop the cached default registry. For tests only."""
    global _default_registry
    _default_registry = None


def _strategy_classes_in(module: object) -> tuple[type[StrategyBase], ...]:
    """Concrete ``StrategyBase`` subclasses defined by ``module`` itself.

    Filtered on ``__module__`` so a strategy that imports another strategy for
    reuse does not get registered twice under two module paths.
    """
    found: list[type[StrategyBase]] = []
    module_name = getattr(module, "__name__", "")
    for attribute in vars(module).values():
        if (
            isinstance(attribute, type)
            and issubclass(attribute, StrategyBase)
            and attribute is not StrategyBase
            and attribute.__module__ == module_name
        ):
            found.append(attribute)
    return tuple(found)
