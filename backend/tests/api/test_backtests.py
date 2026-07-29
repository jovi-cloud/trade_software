"""Backtest execution API contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

STRATEGY_PAYLOAD = {
    "name": "Opening Range Breakout",
    "description": "Buys the breakout of the first 15-minute range.",
    "market_type": "equity",
    "instrument": "NIFTY",
    "timeframe": "15m",
    "status": "draft",
    "confidence_level": 5,
    "priority": "medium",
}

VALID_CSV = (
    b"timestamp,open,high,low,close,volume\n"
    b"2024-01-01 09:15:00,100,101,99,100.5,1000\n"
    b"2024-01-01 09:16:00,100.5,102,100,101.5,1200\n"
    b"2024-01-01 09:17:00,101.5,103,101,102.5,900\n"
)

STRATEGY_CODE = """
class Strategy:
    def on_bar(self, bar):
        self.ctx.log(bar.close)
"""


def _create_strategy(client: TestClient) -> str:
    response = client.post("/api/v1/strategies", json=STRATEGY_PAYLOAD)
    assert response.status_code == 201
    return str(response.json()["id"])


def _save_strategy_code(client: TestClient, strategy_id: str, code: str = STRATEGY_CODE) -> None:
    response = client.put(f"/api/v1/strategies/{strategy_id}/code", json={"code": code})
    assert response.status_code == 200


def _import_dataset(client: TestClient) -> str:
    response = client.post(
        "/api/v1/datasets/import",
        data={
            "name": "NIFTY 1m",
            "symbol": "NIFTY",
            "exchange": "NSE",
            "timeframe": "1m",
        },
        files={"file": ("bars.csv", VALID_CSV, "text/csv")},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def test_execute_replays_strategy_against_dataset(client: TestClient) -> None:
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)
    dataset_id = _import_dataset(client)

    response = client.post(
        "/api/v1/backtests/execute",
        json={
            "strategy_id": strategy_id,
            "dataset_id": dataset_id,
            "initial_capital": 100_000,
            "commission": 0.001,
            "slippage": 0.0005,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["completed"] is True
    assert body["bars_processed"] == 3
    assert body["errors"] == []
    assert len(body["strategy_logs"]) == 3
    assert body["execution_time_ms"] >= 0
    assert body["trade_count"] == 0
    assert body["position_closed"] is True
    assert body["orders"] == []
    assert body["trades"] == []
    assert body["metrics"]["total_trades"] == 0
    assert body["metrics"]["net_profit"] == 0.0
    assert body["equity_history"] == []
    assert len(body["candles"]) == 3
    assert body["entry_markers"] == []
    assert body["exit_markers"] == []


def test_execute_missing_strategy_returns_404(client: TestClient) -> None:
    dataset_id = _import_dataset(client)

    response = client.post(
        "/api/v1/backtests/execute",
        json={"strategy_id": "missing", "dataset_id": dataset_id},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_execute_missing_dataset_returns_404(client: TestClient) -> None:
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)

    response = client.post(
        "/api/v1/backtests/execute",
        json={"strategy_id": strategy_id, "dataset_id": "missing"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_execute_without_saved_code_returns_422(client: TestClient) -> None:
    strategy_id = _create_strategy(client)
    dataset_id = _import_dataset(client)

    response = client.post(
        "/api/v1/backtests/execute",
        json={"strategy_id": strategy_id, "dataset_id": dataset_id},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_execute_with_trades_returns_chart_markers(client: TestClient) -> None:
    strategy_id = _create_strategy(client)
    code = """
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(10)
        elif bar.close > 101:
            self.ctx.close()
"""
    _save_strategy_code(client, strategy_id, code)
    dataset_id = _import_dataset(client)

    response = client.post(
        "/api/v1/backtests/execute",
        json={"strategy_id": strategy_id, "dataset_id": dataset_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trade_count"] == 1
    assert len(body["entry_markers"]) == 1
    assert len(body["exit_markers"]) == 1
    assert body["entry_markers"][0]["marker_kind"] == "entry"
    assert body["exit_markers"][0]["marker_kind"] == "exit"
    assert len(body["equity_history"]) == 1


def test_execute_rejects_invalid_capital(client: TestClient) -> None:
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)
    dataset_id = _import_dataset(client)

    response = client.post(
        "/api/v1/backtests/execute",
        json={
            "strategy_id": strategy_id,
            "dataset_id": dataset_id,
            "initial_capital": 0,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
