"""Dataset Library API contract: status codes + response shape."""

from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient
from httpx import Response

VALID_CSV = (
    b"timestamp,open,high,low,close,volume\n"
    b"2024-01-01 09:15:00,100,101,99,100.5,1000\n"
    b"2024-01-01 09:16:00,100.5,102,100,101.5,1200\n"
    b"2024-01-01 09:17:00,101.5,103,101,102.5,900\n"
)


def _import(
    client: TestClient,
    *,
    name: str = "NIFTY 1m",
    symbol: str = "NIFTY",
    exchange: str = "NSE",
    timeframe: str = "1m",
    content: bytes = VALID_CSV,
    filename: str = "bars.csv",
) -> Response:
    return cast(
        Response,
        client.post(
            "/api/v1/datasets/import",
            data={"name": name, "symbol": symbol, "exchange": exchange, "timeframe": timeframe},
            files={"file": (filename, content, "text/csv")},
        ),
    )


def test_import_creates_completed_dataset(client: TestClient) -> None:
    response = _import(client)

    assert response.status_code == 201
    body = response.json()
    assert body["import_status"] == "completed"
    assert body["symbol"] == "NIFTY"
    assert body["row_count"] == 3
    assert body["validation_report"]["total_rows"] == 3
    assert body["quality_score"] is not None
    assert body["quality_score"] >= 70


def test_import_with_missing_columns_returns_failed_dataset(client: TestClient) -> None:
    bad_csv = b"timestamp,open,high,low,close\n2024-01-01 09:15:00,1,2,3,4\n"

    response = _import(client, content=bad_csv, filename="bad.csv")

    assert response.status_code == 201
    body = response.json()
    assert body["import_status"] == "failed"
    assert body["validation_report"] is None
    # The report cannot be built, so the message must name the missing column.
    assert "volume" in body["import_error"]


def test_successful_import_has_no_import_error(client: TestClient) -> None:
    body = _import(client).json()

    assert body["import_error"] is None
    assert body["validation_report"] is not None


def test_import_rejects_blank_name(client: TestClient) -> None:
    response = _import(client, name="   ")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_dataset(client: TestClient) -> None:
    created = _import(client).json()

    response = client.get(f"/api/v1/datasets/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_missing_dataset_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_list_supports_search_and_sort(client: TestClient) -> None:
    _import(client, name="NIFTY 1m", symbol="NIFTY")
    _import(client, name="BTC 1m", symbol="BTCUSD")

    response = client.get("/api/v1/datasets", params={"q": "btc"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["symbol"] == "BTCUSD"


def test_delete_removes_dataset(client: TestClient) -> None:
    created = _import(client).json()

    response = client.delete(f"/api/v1/datasets/{created['id']}")
    assert response.status_code == 204

    assert client.get(f"/api/v1/datasets/{created['id']}").status_code == 404


def test_preview_returns_head_and_tail_rows(client: TestClient) -> None:
    created = _import(client).json()

    head = client.get(
        f"/api/v1/datasets/{created['id']}/preview", params={"part": "head", "rows": 2}
    )
    tail = client.get(
        f"/api/v1/datasets/{created['id']}/preview", params={"part": "tail", "rows": 2}
    )

    assert head.status_code == 200
    assert len(head.json()["rows"]) == 2
    assert head.json()["rows"][0]["open"] == 100.0

    assert tail.status_code == 200
    assert len(tail.json()["rows"]) == 2
    assert tail.json()["rows"][-1]["open"] == 101.5


def test_list_bars_returns_paginated_rows(client: TestClient) -> None:
    created = _import(client).json()

    response = client.get(
        f"/api/v1/datasets/{created['id']}/bars",
        params={"offset": 0, "limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["offset"] == 0
    assert body["limit"] == 2
    assert len(body["rows"]) == 2
    assert body["rows"][0]["open"] == 100.0


def test_validate_reruns_validation_from_stored_csv(client: TestClient) -> None:
    created = _import(client).json()

    response = client.post(f"/api/v1/datasets/{created['id']}/validate")

    assert response.status_code == 200
    body = response.json()
    assert body["import_status"] == "completed"
    assert body["row_count"] == 3


def test_clean_dataset_removes_outside_session_bars(client: TestClient) -> None:
    csv = (
        b"timestamp,open,high,low,close,volume\n"
        b"2024-01-01 09:15:00,100,101,99,100.5,1000\n"
        b"2024-01-01 08:00:00,100,101,99,100.5,1000\n"
        b"2024-01-01 09:17:00,101.5,103,101,102.5,900\n"
    )
    created = _import(client, content=csv).json()

    response = client.post(
        f"/api/v1/datasets/{created['id']}/clean",
        json={
            "remove_outside_session": True,
            "remove_weekend_bars": False,
            "remove_holiday_bars": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 2
    assert body["current_version_number"] == 2
    session = body["pipeline_report"]["session"]
    assert session["candles_outside_session"] == 0


def test_clean_dataset_removes_price_anomaly_days(client: TestClient) -> None:
    csv = (
        b"timestamp,open,high,low,close,volume\n"
        b"2024-01-01 09:15:00,100,101,99,100,1000\n"
        b"2024-01-01 09:17:00,100,101,99,100,1000\n"
        b"2024-01-01 09:19:00,120,125,119,125,1000\n"
        b"2024-01-02 09:15:00,100,101,99,100,1000\n"
        b"2024-01-02 09:17:00,100,101,99,100,1000\n"
    )
    created = _import(client, content=csv).json()
    anomalies = created["pipeline_report"]["price_anomalies"]
    assert anomalies["spikes_over_10_pct"] == 1
    assert anomalies["intraday_days_over_10_samples"] == ["2024-01-01"]

    response = client.post(
        f"/api/v1/datasets/{created['id']}/clean",
        json={
            "remove_outside_session": False,
            "remove_weekend_bars": False,
            "remove_holiday_bars": False,
            "remove_intraday_spike_days_over_10pct": True,
            "remove_intraday_spike_days_over_20pct": False,
            "remove_cross_day_spike_days_over_10pct": False,
            "remove_cross_day_spike_days_over_20pct": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 2
    assert body["pipeline_report"]["price_anomalies"]["spikes_over_10_pct"] == 0


def test_validate_missing_dataset_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/datasets/does-not-exist/validate")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
