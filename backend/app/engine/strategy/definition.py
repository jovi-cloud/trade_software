"""A registered strategy: its class, its declaration, and its verdict.

``StrategyDefinition`` is what the registry stores and what every layer above
the engine reads. It carries the validation report alongside the class so a
caller can list an invalid strategy and explain *why* it is invalid, rather than
the library silently having nine entries instead of ten.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.explain import ExplainLevel
from app.engine.strategy.framework import StrategyBase
from app.engine.strategy.metadata import StrategyMetadata
from app.engine.strategy.params import (
    ParamSpec,
    ParamValidationReport,
    ParamValue,
    default_values,
    resolve_params,
)
from app.engine.strategy.risk import RiskRules
from app.engine.strategy.validation import (
    StrategyValidationReport,
    validate_strategy_class,
)


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    """One entry in the strategy library."""

    strategy_class: type[StrategyBase]
    metadata: StrategyMetadata
    parameters: tuple[ParamSpec, ...]
    validation: StrategyValidationReport
    #: Dotted module path the class was loaded from, for the docs and debugging.
    module: str

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def is_valid(self) -> bool:
        return self.validation.is_valid

    @property
    def traces_conditions(self) -> bool:
        """Does running this strategy fill the Decision Inspector?

        ``StrategyBase.on_bar`` is the only thing that routes rules through
        ``check()``, and ``check()`` is the only source of condition traces. A
        class that replaced ``on_bar`` has opted out, so there would be nothing
        for the extra collection to record.
        """
        return getattr(self.strategy_class, "on_bar", None) is StrategyBase.on_bar

    @property
    def recommended_explain_level(self) -> ExplainLevel:
        """The lowest level that still captures everything this strategy exposes.

        Read by the run workflow to pick a default: collecting only trades from
        a strategy that traces its conditions throws away the answer to "why
        did nothing happen on this bar", which is the question the Decision
        Inspector exists for.
        """
        return ExplainLevel.FULL if self.traces_conditions else ExplainLevel.TRADES_ONLY

    @property
    def parameter_groups(self) -> tuple[str, ...]:
        """Group names in the order the parameter editor should render them."""
        ordered: list[str] = []
        for spec in self.sorted_parameters:
            if spec.group not in ordered:
                ordered.append(spec.group)
        return tuple(ordered)

    @property
    def sorted_parameters(self) -> tuple[ParamSpec, ...]:
        """Parameters in display order: by group first seen, then display_order."""
        group_order = {spec.group: index for index, spec in enumerate(self.parameters)}
        return tuple(
            sorted(
                self.parameters,
                key=lambda spec: (group_order[spec.group], spec.display_order, spec.name),
            )
        )

    def default_params(self) -> dict[str, ParamValue]:
        return default_values(self.parameters)

    def validate_params(self, values: Mapping[str, object] | None) -> ParamValidationReport:
        """Check trader-supplied values without instantiating the strategy."""
        return resolve_params(self.parameters, values)

    def instantiate(self, params: Mapping[str, object] | None = None) -> StrategyBase:
        """Build a runnable instance. Raises ``StrategyParameterError`` on bad values."""
        return self.strategy_class(params)

    def snapshot(self, params: Mapping[str, ParamValue]) -> str:
        """A deterministic, human-readable record of what was run.

        Persisted on a backtest run in place of the source text a hand-written
        strategy would have. It is what makes a library run reproducible six
        months later: the id and version pin the code, the resolved parameters
        pin the configuration, and both are sorted so the same run always
        hashes to the same value.
        """
        lines = [
            f"# Strategy Library: {self.metadata.id}@{self.metadata.version}",
            f"# Name: {self.metadata.name}",
            f"# Module: {self.module}",
            "# Resolved parameters:",
        ]
        lines.extend(f"#   {name} = {params[name]!r}" for name in sorted(params))
        return "\n".join(lines) + "\n"

    def declared_risk(self, params: Mapping[str, object] | None = None) -> RiskRules:
        """Risk rules a given configuration would use, for the docs page.

        Built from a throwaway instance because risk rules can depend on
        parameters (an ATR multiple, a session exit time).
        """
        return self.instantiate(params).declare_risk()


def build_definition(strategy_class: type[StrategyBase]) -> StrategyDefinition:
    """Audit a strategy class and wrap it as a definition.

    Reads ``metadata`` defensively: a class that forgot to declare it should
    produce a validation error, not an ``AttributeError`` that takes the whole
    library down with it.
    """
    metadata = getattr(strategy_class, "metadata", None)
    if not isinstance(metadata, StrategyMetadata):
        metadata = None

    parameters = tuple(getattr(strategy_class, "parameters", ()) or ())
    strategy_id = metadata.id if metadata is not None else _fallback_id(strategy_class)

    report = validate_strategy_class(
        strategy_id=strategy_id,
        metadata=metadata,
        parameters=parameters,
        has_entry_rule=_overrides(strategy_class, "entry_signal"),
        has_exit_rule=_overrides(strategy_class, "exit_signal"),
    )

    return StrategyDefinition(
        strategy_class=strategy_class,
        metadata=metadata if metadata is not None else _placeholder_metadata(strategy_id),
        parameters=parameters,
        validation=report,
        module=strategy_class.__module__,
    )


def _overrides(strategy_class: type[StrategyBase], hook: str) -> bool:
    """Did this class provide its own implementation of a base hook?"""
    return getattr(strategy_class, hook, None) is not getattr(StrategyBase, hook, None)


def _fallback_id(strategy_class: type[StrategyBase]) -> str:
    """Derive an id for a class that declared no metadata, so it is still listable."""
    name = strategy_class.__name__
    parts: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0:
            parts.append("_")
        parts.append(char.lower())
    return "".join(parts)


def _placeholder_metadata(strategy_id: str) -> StrategyMetadata:
    """Minimal metadata so an invalid strategy can still be listed and explained."""
    from app.domain.enums import RiskLevel, StrategyCategory
    from app.engine.strategy.metadata import StrategyDocumentation

    return StrategyMetadata(
        id=strategy_id,
        name=strategy_id,
        description="",
        version="0.0.0",
        author="",
        category=StrategyCategory.TREND_FOLLOWING,
        markets=(),
        timeframes=(),
        tags=(),
        risk_level=RiskLevel.MEDIUM,
        supports_long=False,
        supports_short=False,
        supports_intraday=False,
        supports_swing=False,
        supports_position_trading=False,
        documentation=StrategyDocumentation(overview=""),
    )
