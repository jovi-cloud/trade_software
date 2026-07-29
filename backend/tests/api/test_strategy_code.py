"""Strategy code editor API contract: status codes + response shape."""

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


def _create_strategy(client: TestClient) -> str:
    response = client.post("/api/v1/strategies", json=STRATEGY_PAYLOAD)
    assert response.status_code == 201
    return str(response.json()["id"])


def test_get_code_seeds_default_template(client: TestClient) -> None:
    strategy_id = _create_strategy(client)

    response = client.get(f"/api/v1/strategies/{strategy_id}/code")

    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == strategy_id
    assert "class Strategy:" in body["code"]
    assert body["compiled_successfully"] is True
    assert body["compile_error"] is None


def test_get_code_missing_strategy_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/strategies/does-not-exist/code")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_put_code_saves_and_reports_syntax_result(client: TestClient) -> None:
    strategy_id = _create_strategy(client)

    response = client.put(
        f"/api/v1/strategies/{strategy_id}/code",
        json={"code": "class Strategy:\n    def on_start(self):\n        pass\n"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["compiled_successfully"] is True

    fetched = client.get(f"/api/v1/strategies/{strategy_id}/code")
    assert "def on_start" in fetched.json()["code"]


def test_put_code_with_syntax_error_saves_but_flags_invalid(client: TestClient) -> None:
    strategy_id = _create_strategy(client)

    response = client.put(
        f"/api/v1/strategies/{strategy_id}/code", json={"code": "def broken(:\n    pass"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["compiled_successfully"] is False
    assert body["compile_error"] is not None


def test_validate_returns_syntax_valid(client: TestClient) -> None:
    strategy_id = _create_strategy(client)

    response = client.post(
        f"/api/v1/strategies/{strategy_id}/validate",
        json={"code": "class Strategy:\n    def on_start(self):\n        pass\n"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["error"] is None


def test_validate_returns_line_column_and_message_on_syntax_error(client: TestClient) -> None:
    strategy_id = _create_strategy(client)

    response = client.post(
        f"/api/v1/strategies/{strategy_id}/validate",
        json={"code": "def broken(:\n    pass"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["error"]["line"] == 1
    assert body["error"]["column"] is not None
    assert body["error"]["message"]


def test_validate_missing_strategy_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/strategies/does-not-exist/validate", json={"code": "pass"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_validate_does_not_execute_code(client: TestClient) -> None:
    """A syntax-valid payload that would raise if executed must still report valid."""
    strategy_id = _create_strategy(client)

    response = client.post(
        f"/api/v1/strategies/{strategy_id}/validate",
        json={"code": "import os\nos.system('echo should-not-run')\nraise RuntimeError('boom')\n"},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
