"""Cached snapshot of a persisted backtest run for bar-level inspection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.paths import DataPaths
from app.engine.explain.event_index import EventIndex
from app.engine.explain.serialize import events_from_json_list
from app.repositories.backtest_run_repo import BacktestRunRepository


@dataclass(frozen=True)
class RunSnapshot:
    run_id: str
    bar_count: int
    candles: list[dict[str, Any]]
    orders: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    event_index: EventIndex


class RunSnapshotCache:
    """Loads run JSON once and reuses indexes for bar inspection."""

    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.repo = BacktestRunRepository(session)
        self._cache: dict[str, RunSnapshot] = {}

    def get(self, run_id: str) -> RunSnapshot:
        cached = self._cache.get(run_id)
        if cached is not None:
            return cached
        row = self.repo.get(run_id)
        if row is None:
            raise NotFoundError(f"Backtest run '{run_id}' not found")
        run = row[0]
        candles: list[dict[str, Any]] = json.loads(run.candles_json)
        orders: list[dict[str, Any]] = json.loads(run.orders_json)
        trades: list[dict[str, Any]] = json.loads(run.trades_json)
        events = events_from_json_list(json.loads(run.explain_events_json))
        snapshot = RunSnapshot(
            run_id=run_id,
            bar_count=len(candles),
            candles=candles,
            orders=orders,
            trades=trades,
            event_index=EventIndex.build(events),
        )
        self._cache[run_id] = snapshot
        return snapshot

    def clear(self, run_id: str | None = None) -> None:
        if run_id is None:
            self._cache.clear()
            return
        self._cache.pop(run_id, None)
