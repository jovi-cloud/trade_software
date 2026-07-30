"""Strategy Library API contract."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_library_strategies(client: TestClient) -> None:
    response = client.get("/api/v1/strategy-library")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 10
    assert len(body["items"]) >= 10
    first = body["items"][0]
    assert {"id", "name", "description", "version", "category", "is_valid"} <= set(first)


def test_library_facets(client: TestClient) -> None:
    response = client.get("/api/v1/strategy-library/facets")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 10
    assert body["valid_count"] >= 10
    assert body["categories"]


def test_get_library_strategy(client: TestClient) -> None:
    response = client.get("/api/v1/strategy-library/ema_crossover")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "ema_crossover"
    assert body["name"] == "EMA Crossover"
    assert body["parameters"]
    assert body["validation"]["is_valid"] is True


def test_get_library_strategy_parameters(client: TestClient) -> None:
    response = client.get("/api/v1/strategy-library/ema_crossover/parameters")
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "ema_crossover"
    assert body["parameters"]
    assert body["defaults"]


def test_get_library_strategy_documentation(client: TestClient) -> None:
    response = client.get("/api/v1/strategy-library/ema_crossover/documentation")
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "ema_crossover"
    assert body["overview"]
    assert body["markdown"].startswith("# EMA Crossover")
    assert body["parameters"]


def test_validate_library_strategy_params(client: TestClient) -> None:
    response = client.post(
        "/api/v1/strategy-library/ema_crossover/validate",
        json={"params": {}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"] == "ema_crossover"
    assert body["is_valid"] is True
    assert body["resolved_params"]


def test_validate_rejects_out_of_range_params(client: TestClient) -> None:
    response = client.post(
        "/api/v1/strategy-library/ema_crossover/validate",
        json={"params": {"fast_period": 1_000}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is False
    assert body["errors"]


def test_get_missing_library_strategy_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/strategy-library/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_search_filters_library_strategies(client: TestClient) -> None:
    response = client.get(
        "/api/v1/strategy-library",
        params={"q": "ema", "category": "trend_following"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(
        "ema" in item["name"].lower() or item["id"] == "ema_crossover" for item in body["items"]
    )
