"""Bar inspection API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.test_backtests import _create_strategy, _import_dataset, _save_strategy_code

TRADING_STRATEGY = """
class Strategy:
    def on_bar(self, bar):
        rsi = 55
        ema_fast = bar.close
        ema_slow = bar.open
        self.ctx.trace_indicator("RSI", rsi)
        self.ctx.trace_condition(
            "EMA20 > EMA50",
            actual=f"{ema_fast} > {ema_slow}",
            expected="True",
            passed=ema_fast > ema_slow,
        )
        if self.ctx.position is None:
            self.ctx.buy(10)
        elif bar.close > self.ctx.position.entry_price:
            self.ctx.close()
"""


def _execute_run(client: TestClient) -> str:
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
    run_id = response.json()["run_id"]
    assert isinstance(run_id, str)
    return run_id


def test_get_run_bar_returns_decision_and_conditions(client: TestClient) -> None:
    run_id = _execute_run(client)
    response = client.get(f"/api/v1/backtests/runs/{run_id}/bars/0")
    assert response.status_code == 200
    body = response.json()
    assert body["bar_index"] == 0
    assert body["candle"]["close"] > 0
    assert body["decision"]["decision_type"] in {
        "buy",
        "no_trade",
        "hold",
        "rejected",
        "sell",
        "exit",
    }
    assert "navigation" in body
    assert body["navigation"]["bar_count"] == 3


def test_list_run_bar_events(client: TestClient) -> None:
    run_id = _execute_run(client)
    bar = client.get(f"/api/v1/backtests/runs/{run_id}/bars/1").json()
    response = client.get(f"/api/v1/backtests/runs/{run_id}/bars/1/events")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(bar["event_seqs"])


def test_get_run_bar_rejects_out_of_range(client: TestClient) -> None:
    run_id = _execute_run(client)
    response = client.get(f"/api/v1/backtests/runs/{run_id}/bars/99")
    assert response.status_code == 422
