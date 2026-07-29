"""Engine validation API."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_engine_validation_report_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/system/engine-validation")
    assert response.status_code == 200
    body = response.json()
    assert body["failed_count"] == 0
    assert body["coverage_pct"] == 100.0
    assert body["deterministic"]["passed"] is True
    assert len(body["scenarios"]) >= 13
