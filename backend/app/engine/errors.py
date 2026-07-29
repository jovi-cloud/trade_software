"""Engine exception hierarchy.

Framework-free: these know nothing about HTTP. ``ExecutionEngine.run`` catches
them and reports them on the ``ExecutionResult`` rather than letting them
escape, so a broken strategy is a result the user can read, not a 500.
"""

from __future__ import annotations


class EngineError(Exception):
    """Base for every error the engine raises deliberately."""


class StrategyCompileError(EngineError):
    """Source failed to compile, or did not define a usable ``Strategy`` class."""

    def __init__(self, message: str, *, line: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.line = line


class StrategyRuntimeError(EngineError):
    """Strategy code raised while one of its lifecycle hooks was running."""

    def __init__(self, message: str, *, hook: str, bar_index: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hook = hook
        self.bar_index = bar_index
