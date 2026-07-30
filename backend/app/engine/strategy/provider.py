"""How the engine obtains a strategy instance.

Two kinds of strategy now exist, and the engine must not care which it is
running:

* **User source text** - typed into the editor, stored in the database, compiled
  in a restricted namespace with no imports (``loader.py``). This is the path
  every run before the Strategy Framework took, and it is unchanged.
* **A library strategy** - a real, importable ``StrategyBase`` subclass under
  ``library/``, instantiated with validated parameters. It can import the
  indicator library, which is exactly why library strategies are classes rather
  than source strings: ten strategies re-deriving Wilder's ATR inline would be
  ten chances to get it subtly different.

Both converge on ``LoadedStrategy``, which is what ``runner.py`` already
programs against. The bar loop, the simulator, the portfolio and every metric
are untouched - the engine gained one way to be *handed* a strategy, not a
second way to run one.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from app.engine.context import LogCollector
from app.engine.errors import StrategyCompileError
from app.engine.strategy.base import LoadedStrategy
from app.engine.strategy.framework import StrategyBase
from app.engine.strategy.loader import StrategyLoader
from app.engine.strategy.params import StrategyParameterError


@runtime_checkable
class StrategyProvider(Protocol):
    """Anything that can produce a runnable strategy for one run."""

    def load(self, logs: LogCollector) -> LoadedStrategy:
        """Build the strategy. Raise ``StrategyCompileError`` if it cannot be built."""

    def describe(self) -> str:
        """Short identity string for logs and run snapshots."""


class SourceStrategyProvider:
    """Compiles user source text through the existing restricted-namespace loader."""

    def __init__(self, source: str) -> None:
        self._source = source

    def load(self, logs: LogCollector) -> LoadedStrategy:
        return StrategyLoader(logs).load(self._source)

    def describe(self) -> str:
        return "user source"


class LibraryStrategyProvider:
    """Instantiates a registered library strategy with validated parameters.

    Parameter errors surface as ``StrategyCompileError`` so a misconfigured
    library strategy fails the same way a syntactically broken user strategy
    does: as a readable error on the run result, not an exception escaping the
    engine.
    """

    def __init__(
        self,
        strategy_class: type[StrategyBase],
        params: Mapping[str, object] | None = None,
        *,
        strategy_id: str | None = None,
        version: str | None = None,
    ) -> None:
        self._strategy_class = strategy_class
        self._params = dict(params or {})
        self._strategy_id = strategy_id or getattr(
            getattr(strategy_class, "metadata", None), "id", strategy_class.__name__
        )
        self._version = version or getattr(
            getattr(strategy_class, "metadata", None), "version", "0.0.0"
        )

    def load(self, logs: LogCollector) -> LoadedStrategy:
        try:
            instance = self._strategy_class(self._params)
        except StrategyParameterError as exc:
            raise StrategyCompileError(exc.message) from exc
        except Exception as exc:
            raise StrategyCompileError(
                f"Strategy '{self._strategy_id}' could not be instantiated: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        return LoadedStrategy(instance)

    def describe(self) -> str:
        return f"library:{self._strategy_id}@{self._version}"

    @property
    def params(self) -> Mapping[str, object]:
        return dict(self._params)
