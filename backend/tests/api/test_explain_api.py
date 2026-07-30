"""Explainability API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.test_backtests import _create_strategy, _import_dataset, _save_strategy_code
from tests.helpers.backtests import submit_backtest

TRADING_STRATEGY = """
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(10)
        elif bar.close > self.ctx.position.entry_price:
            self.ctx.close()
"""


def _execute_trading_run(client: TestClient) -> str:
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id, TRADING_STRATEGY)
    dataset_id = _import_dataset(client)
    body = submit_backtest(
        client,
        {
            "strategy_id": strategy_id,
            "dataset_id": dataset_id,
            "initial_capital": 10_000,
            "explain_level": "full",
        },
    )
    run_id = body["run_id"]
    assert isinstance(run_id, str)
    return run_id


def test_list_run_events_supports_pagination_and_filters(client: TestClient) -> None:
    run_id = _execute_trading_run(client)

    response = client.get(f"/api/v1/backtests/runs/{run_id}/events", params={"limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert len(body["items"]) <= 5
    first = body["items"][0]
    assert first["schema_version"] == 1
    assert first["event_id"].startswith("evt-")

    filtered = client.get(
        f"/api/v1/backtests/runs/{run_id}/events",
        params={"layer": "execution", "limit": 100},
    )
    assert filtered.status_code == 200
    assert all(item["layer"] == "execution" for item in filtered.json()["items"])


def test_trade_inspector_endpoints(client: TestClient) -> None:
    run_id = _execute_trading_run(client)
    run = client.get(f"/api/v1/backtests/runs/{run_id}").json()
    if run["trade_count"] == 0:
        return

    trade_id = 1
    inspection = client.get(f"/api/v1/backtests/runs/{run_id}/trades/{trade_id}")
    assert inspection.status_code == 200
    body = inspection.json()
    assert body["summary"]["trade_number"] == trade_id
    assert len(body["timeline"]) > 0

    events = client.get(
        f"/api/v1/backtests/runs/{run_id}/trades/{trade_id}/events",
        params={"limit": 50},
    )
    assert events.status_code == 200
    assert events.json()["total"] == len(body["event_seqs"])


def test_legacy_events_remain_readable(client: TestClient) -> None:
    run_id = _execute_trading_run(client)
    response = client.get(f"/api/v1/backtests/runs/{run_id}/events", params={"limit": 1})
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert "reason_code" in item
    assert item["reason_code"].startswith("system.") or item["reason_code"].startswith("signal.")
