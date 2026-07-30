"""Explain events on backtest execution API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.test_backtests import (
    _create_strategy,
    _import_dataset,
    _save_strategy_code,
)
from tests.helpers.backtests import run_backtest, run_events, submit_backtest

TRADING_STRATEGY = """
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(10)
        elif bar.close > self.ctx.position.entry_price:
            self.ctx.close()
"""


def test_execute_returns_structured_explain_events(client: TestClient) -> None:
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id, TRADING_STRATEGY)
    dataset_id = _import_dataset(client)

    body = submit_backtest(
        client,
        {
            "strategy_id": strategy_id,
            "dataset_id": dataset_id,
            "initial_capital": 10_000,
            "explain_level": "trades_only",
        },
    )
    assert body["explain_level"] == "trades_only"

    events = run_events(client, body["run_id"])
    assert len(events) > 0
    event_types = {event["event_type"] for event in events}
    assert "run_started" in event_types
    assert "dataset_loaded" in event_types
    assert "run_completed" in event_types
    first = events[0]
    assert "message" in first
    assert "reason_code" in first
    assert "layer" in first


def test_run_detail_carries_the_lifecycle_but_not_the_per_bar_log(client: TestClient) -> None:
    """The run detail is bounded; the full log lives behind pagination.

    Inlining every event made a single intraday run a 28 MB response and 55,000
    rendered rows, so the detail keeps only the run's own lifecycle.
    """
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id, TRADING_STRATEGY)
    dataset_id = _import_dataset(client)

    detail = run_backtest(
        client,
        {"strategy_id": strategy_id, "dataset_id": dataset_id, "initial_capital": 10_000},
    )

    assert "explain_events" not in detail
    layers = {event["layer"] for event in detail["lifecycle_events"]}
    assert layers == {"system"}
    assert {event["event_type"] for event in detail["lifecycle_events"]} >= {
        "run_started",
        "dataset_loaded",
        "run_completed",
    }
    # The execution-layer events the detail no longer inlines are still served.
    execution_events = run_events(client, detail["id"], layer="execution")
    assert execution_events
