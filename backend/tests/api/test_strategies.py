"""Strategy Library API contract: status codes + response shape."""

from __future__ import annotations

from fastapi.testclient import TestClient

PAYLOAD = {
    "name": "Opening Range Breakout",
    "description": "Buys the breakout of the first 15-minute range.",
    "hypothesis": "Early volatility expansion tends to continue intraday.",
    "market_type": "equity",
    "instrument": "NIFTY",
    "timeframe": "15m",
    "entry_rules": "Buy on a 5m close above the first 15m high.",
    "exit_rules": "Exit at session close or stop, whichever first.",
    "stop_loss_method": "Below the opening range low.",
    "target_method": "2R fixed target.",
    "position_sizing": "1% account risk per trade.",
    "assumptions": "Liquidity is sufficient to fill at the breakout price.",
    "known_weaknesses": "Chops in low-volatility opens.",
    "ideas_for_improvement": "Add a volume filter on the breakout bar.",
    "status": "draft",
    "confidence_level": 6,
    "priority": "medium",
    "tags": "intraday, breakout",
}


def test_create_and_get_strategy(client: TestClient) -> None:
    created = client.post("/api/v1/strategies", json=PAYLOAD)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == PAYLOAD["name"]
    assert body["status"] == "draft"

    fetched = client.get(f"/api/v1/strategies/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_create_rejects_duplicate_name(client: TestClient) -> None:
    client.post("/api/v1/strategies", json=PAYLOAD)
    response = client.post("/api/v1/strategies", json=PAYLOAD)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_create_rejects_blank_name(client: TestClient) -> None:
    response = client.post("/api/v1/strategies", json={**PAYLOAD, "name": "   "})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_missing_strategy_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/strategies/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_create_rejects_out_of_range_confidence_level(client: TestClient) -> None:
    response = client.post("/api/v1/strategies", json={**PAYLOAD, "confidence_level": 11})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_supports_search_status_filter_and_sort(client: TestClient) -> None:
    client.post("/api/v1/strategies", json=PAYLOAD)
    client.post(
        "/api/v1/strategies",
        json={
            **PAYLOAD,
            "name": "Mean Reversion BTC",
            "instrument": "BTCUSD",
            "market_type": "crypto",
            "status": "testing",
        },
    )

    response = client.get("/api/v1/strategies", params={"status": "testing"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Mean Reversion BTC"

    response = client.get("/api/v1/strategies", params={"q": "opening"})
    assert response.json()["total"] == 1


def test_update_strategy(client: TestClient) -> None:
    created = client.post("/api/v1/strategies", json=PAYLOAD).json()

    response = client.patch(
        f"/api/v1/strategies/{created['id']}", json={"status": "validated", "tags": None}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated"
    assert body["tags"] is None


def test_delete_is_soft_and_hides_strategy_from_get(client: TestClient) -> None:
    created = client.post("/api/v1/strategies", json=PAYLOAD).json()

    response = client.delete(f"/api/v1/strategies/{created['id']}")
    assert response.status_code == 204

    assert client.get(f"/api/v1/strategies/{created['id']}").status_code == 404


def test_stats_reflects_created_strategies(client: TestClient) -> None:
    client.post("/api/v1/strategies", json=PAYLOAD)
    client.post(
        "/api/v1/strategies",
        json={**PAYLOAD, "name": "Second", "status": "testing", "priority": "high"},
    )

    response = client.get("/api/v1/strategies/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["draft"] == 1
    assert body["testing"] == 1
    assert len(body["recent_research"]) == 2
    assert [s["name"] for s in body["high_priority"]] == ["Second"]
    assert [s["name"] for s in body["needs_review"]] == ["Second"]
