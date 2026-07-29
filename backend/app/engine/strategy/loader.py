"""Compile strategy source into a runnable object inside a restricted namespace.

## What the restricted namespace is, and what it is not

The namespace below removes the import machinery and every builtin that
reaches the outside world, so a strategy cannot open files, spawn processes,
open sockets, or ``import`` anything. That stops *accidents* - the pasted
snippet with a stray ``import requests``, the ``open()`` left in from a
notebook - and makes the intended API the obvious path.

It is **not** a security sandbox, and must not be described as one. Restricted
builtins are escapable in CPython: ``().__class__.__bases__[0].__subclasses__()``
walks to arbitrary types from a plain tuple literal, and no builtins dict can
prevent that. Anyone who wants out, gets out.

That is consistent with ARCHITECTURE.md's explicit decision - "Sandboxing:
None. Code executes in-process. The trust boundary is you" - which this module
does not overturn. It adds guardrails on top of that trust boundary rather
than pretending to replace it. Running untrusted third-party strategy code
would need a real boundary (subprocess + seccomp, or a container), which is
out of scope for a single-user local tool.
"""

from __future__ import annotations

from typing import Any

from app.engine.context import LogCollector
from app.engine.errors import StrategyCompileError
from app.engine.strategy.base import LoadedStrategy

STRATEGY_CLASS_NAME = "Strategy"

# Deliberately absent: __import__, open, eval, exec, compile, input, exit,
# quit, help, breakpoint, globals, locals, vars, dir, getattr, setattr,
# delattr, memoryview, object, type, super.
#
# __build_class__ is mandatory, not optional: the `class` statement compiles to
# a call to it, so omitting it makes every strategy fail with a bare NameError.
_SAFE_BUILTIN_NAMES: tuple[str, ...] = (
    "__build_class__",
    "abs",
    "all",
    "any",
    "bool",
    "callable",
    "dict",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "format",
    "frozenset",
    "hasattr",
    "hash",
    "int",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "pow",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "slice",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
    # Exceptions, so strategies can guard their own arithmetic.
    "ArithmeticError",
    "AttributeError",
    "Exception",
    "IndexError",
    "KeyError",
    "RuntimeError",
    "StopIteration",
    "TypeError",
    "ValueError",
    "ZeroDivisionError",
)


def _safe_builtins() -> dict[str, Any]:
    import builtins

    return {name: getattr(builtins, name) for name in _SAFE_BUILTIN_NAMES}


class StrategyLoader:
    """Turns strategy source text into a ``LoadedStrategy``."""

    def __init__(self, logs: LogCollector) -> None:
        self._logs = logs

    def _namespace(self) -> dict[str, Any]:
        namespace: dict[str, Any] = {
            "__builtins__": _safe_builtins(),
            # Required for class creation; a dunder-name the class records.
            "__name__": "strategy",
        }
        # print() is the reflex for "show me what's happening". Rather than
        # fail with a NameError, route it into the run's log so it shows up in
        # the result where the user is already looking.
        namespace["__builtins__"]["print"] = self._captured_print
        return namespace

    def _captured_print(self, *parts: object, **_kwargs: object) -> None:
        self._logs.add(" ".join(str(part) for part in parts))

    def load(self, source: str) -> LoadedStrategy:
        """Compile, execute and instantiate. Raises ``StrategyCompileError``."""
        if not source.strip():
            raise StrategyCompileError("Strategy source is empty")

        try:
            code = compile(source, "<strategy>", "exec")
        except SyntaxError as exc:
            raise StrategyCompileError(f"Syntax error: {exc.msg}", line=exc.lineno) from exc
        except ValueError as exc:
            # e.g. source containing null bytes
            raise StrategyCompileError(f"Source could not be compiled: {exc}") from exc

        namespace = self._namespace()
        try:
            exec(code, namespace)
        except Exception as exc:
            raise StrategyCompileError(
                f"Strategy module failed to execute: {type(exc).__name__}: {exc}"
            ) from exc

        strategy_class = namespace.get(STRATEGY_CLASS_NAME)
        if strategy_class is None:
            raise StrategyCompileError(
                f"No class named '{STRATEGY_CLASS_NAME}' was defined by this strategy"
            )
        if not isinstance(strategy_class, type):
            raise StrategyCompileError(f"'{STRATEGY_CLASS_NAME}' must be a class")

        try:
            instance = strategy_class()
        except Exception as exc:
            raise StrategyCompileError(
                f"Strategy() could not be instantiated: {type(exc).__name__}: {exc}"
            ) from exc

        return LoadedStrategy(instance)
