"""Built-in reference strategies.

Every module here contributes one strategy and is discovered automatically by
``StrategyRegistry.discover()`` - there is no list to edit. Modules whose name
starts with an underscore are skipped, which is how ``_shared.py`` stays a
helper rather than becoming a strategy.

These are reference implementations in the literal sense: they are the worked
examples the authoring guide points at, they exercise the full framework
surface (typed parameters, declared risk rules, condition tracing), and they
are covered by tests that run each of them through the real engine.
"""
