"""The Strategy Framework: base class, metadata, parameters, risk, registry.

Two ways to define a strategy, one way to run one:

* **User source text** compiled by ``loader.py`` in a restricted namespace -
  what the code editor saves, unchanged since Phase 2.
* **A library strategy**: a ``StrategyBase`` subclass under ``library/`` that
  declares metadata, typed parameters and risk rules, and implements only
  indicators, conditions, entry rules and exit rules.

Both are handed to ``ExecutionEngine.run`` through a ``StrategyProvider``, so
adding a strategy never touches an engine module.
"""

from app.engine.strategy.base import HOOKS, LoadedStrategy, Strategy
from app.engine.strategy.definition import StrategyDefinition, build_definition
from app.engine.strategy.documentation import (
    StrategyDoc,
    build_documentation,
    render_markdown,
)
from app.engine.strategy.framework import (
    DIRECTION_BOTH,
    DIRECTION_LONG_ONLY,
    DIRECTION_PARAM,
    DIRECTION_SHORT_ONLY,
    SESSION_TIMEZONE_PARAM,
    EntrySignal,
    ExitSignal,
    MarketView,
    SessionSnapshot,
    StrategyBase,
)
from app.engine.strategy.loader import StrategyLoader
from app.engine.strategy.metadata import (
    ChangelogEntry,
    StrategyDocumentation,
    StrategyExample,
    StrategyMetadata,
)
from app.engine.strategy.params import (
    ParamChoice,
    ParamSpec,
    ParamValidationReport,
    ParamValue,
    ParamValues,
    StrategyParameterError,
    ValidationRule,
    default_values,
    resolve_or_raise,
    resolve_params,
    validate_specs,
)
from app.engine.strategy.provider import (
    LibraryStrategyProvider,
    SourceStrategyProvider,
    StrategyProvider,
)
from app.engine.strategy.registry import (
    LIBRARY_PACKAGE,
    LoadFailure,
    StrategyNotFoundError,
    StrategyRegistry,
    get_registry,
    reset_registry,
)
from app.engine.strategy.risk import (
    AtrDistance,
    FixedNotional,
    FixedQuantity,
    PercentDistance,
    PercentOfEquity,
    RiskExit,
    RiskPerTrade,
    RiskRules,
    RMultipleDistance,
)
from app.engine.strategy.validation import (
    StrategyValidationReport,
    ValidationFinding,
    validate_parameter_values,
    validate_registry,
    validate_strategy_class,
)

__all__ = [
    "DIRECTION_BOTH",
    "DIRECTION_LONG_ONLY",
    "DIRECTION_PARAM",
    "DIRECTION_SHORT_ONLY",
    "HOOKS",
    "LIBRARY_PACKAGE",
    "SESSION_TIMEZONE_PARAM",
    "AtrDistance",
    "ChangelogEntry",
    "EntrySignal",
    "ExitSignal",
    "FixedNotional",
    "FixedQuantity",
    "LibraryStrategyProvider",
    "LoadFailure",
    "LoadedStrategy",
    "MarketView",
    "ParamChoice",
    "ParamSpec",
    "ParamValidationReport",
    "ParamValue",
    "ParamValues",
    "PercentDistance",
    "PercentOfEquity",
    "RMultipleDistance",
    "RiskExit",
    "RiskPerTrade",
    "RiskRules",
    "SessionSnapshot",
    "SourceStrategyProvider",
    "Strategy",
    "StrategyBase",
    "StrategyDefinition",
    "StrategyDoc",
    "StrategyDocumentation",
    "StrategyExample",
    "StrategyLoader",
    "StrategyMetadata",
    "StrategyNotFoundError",
    "StrategyParameterError",
    "StrategyProvider",
    "StrategyRegistry",
    "StrategyValidationReport",
    "ValidationFinding",
    "ValidationRule",
    "build_definition",
    "build_documentation",
    "default_values",
    "get_registry",
    "render_markdown",
    "reset_registry",
    "resolve_or_raise",
    "resolve_params",
    "validate_parameter_values",
    "validate_registry",
    "validate_specs",
    "validate_strategy_class",
]
