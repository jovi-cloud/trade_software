"""The strategy contract.

A strategy is a class named ``Strategy`` defining any of three optional
lifecycle hooks::

    class Strategy:
        def on_start(self):
            self.ctx.log("starting")

        def on_bar(self, bar):
            if bar.close > bar.open:
                self.ctx.log(bar.timestamp, "up bar")

        def on_stop(self):
            self.ctx.log("done")

The engine sets ``self.ctx`` (an ``app.engine.context.ExecutionContext``) before
``on_start`` runs.

Strategies cannot import this module - the sandboxed namespace has no import
machinery - so this class is the documented reference for the contract and the
type the engine programs against, not a base users are required to subclass.
The hook signatures match the template shipped in ``StrategyCodeService``, so
strategies saved in earlier phases run unchanged.
"""

from __future__ import annotations

from collections.abc import Callable

from app.engine.bars import Bar
from app.engine.context import ExecutionContext

HOOKS: tuple[str, ...] = ("on_start", "on_bar", "on_stop")


class Strategy:
    """Reference implementation of the strategy contract. Every hook is optional."""

    ctx: ExecutionContext

    def on_start(self) -> None:
        """Called once before the first bar."""

    def on_bar(self, bar: Bar) -> None:
        """Called once per bar, in chronological order."""

    def on_stop(self) -> None:
        """Called once after the final bar."""


class LoadedStrategy:
    """A compiled, instantiated strategy and the hooks it actually defines.

    User strategies are duck-typed rather than required to subclass
    ``Strategy``, so this wrapper resolves the hooks once up front instead of
    doing ``hasattr`` checks inside the bar loop.
    """

    def __init__(self, instance: object) -> None:
        self._instance = instance
        self._on_start = self._resolve("on_start")
        self._on_bar = self._resolve("on_bar")
        self._on_stop = self._resolve("on_stop")

    def _resolve(self, name: str) -> Callable[..., object] | None:
        candidate = getattr(self._instance, name, None)
        return candidate if callable(candidate) else None

    @property
    def defines_on_bar(self) -> bool:
        return self._on_bar is not None

    @property
    def defined_hooks(self) -> tuple[str, ...]:
        resolved = {"on_start": self._on_start, "on_bar": self._on_bar, "on_stop": self._on_stop}
        return tuple(name for name, hook in resolved.items() if hook is not None)

    def bind_context(self, ctx: ExecutionContext) -> None:
        """Strategies read the context as ``self.ctx``."""
        setattr(self._instance, "ctx", ctx)  # noqa: B010

    def call_on_start(self) -> None:
        if self._on_start is not None:
            self._on_start()

    def call_on_bar(self, bar: Bar) -> None:
        if self._on_bar is not None:
            self._on_bar(bar)

    def call_on_stop(self) -> None:
        if self._on_stop is not None:
            self._on_stop()
