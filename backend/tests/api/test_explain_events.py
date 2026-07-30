"""Explain events on backtest execution API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.test_backtests import (
    _create_strategy,
    _import_dataset,
    _save_strategy_code,
)

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

    response = client.post(
        "/api/v1/backtests/execute",
        json={
            "strategy_id": strategy_id,
            "dataset_id": dataset_id,
            "initial_capital": 10_000,
            "explain_level": "trades_only",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["explain_level"] == "trades_only"
    assert len(body["explain_events"]) > 0
    event_types = {event["event_type"] for event in body["explain_events"]}
    assert "run_started" in event_types
    assert "dataset_loaded" in event_types
    assert "run_completed" in event_types
    first = body["explain_events"][0]
    assert "message" in first
    assert "reason_code" in first
    assert "layer" in first
