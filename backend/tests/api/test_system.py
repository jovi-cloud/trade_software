"""Phase 0 smoke tests: the application starts and its wiring holds."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0", "database": "ok"}


def test_openapi_schema_is_served(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/system/health" in response.json()["paths"]


def test_unknown_route_returns_the_standard_error_shape(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
