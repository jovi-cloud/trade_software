"""Aggregates every v1 router. New feature routers are registered here."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import backtest_runs, backtests, datasets, strategies, strategy_code, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(strategies.router)
api_router.include_router(strategy_code.router)
api_router.include_router(datasets.router)
api_router.include_router(backtest_runs.router)
api_router.include_router(backtests.router)

# Phase 1: instruments
# Phase 2: strategy_versions
# Phase 3: jobs, indicators
# Phase 4: results
# Phase 5: notes
