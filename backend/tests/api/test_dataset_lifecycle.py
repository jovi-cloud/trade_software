"""Tests for historical dataset version selection and safe dataset lifecycle."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.test_backtests import _create_strategy, _import_dataset, _save_strategy_code
from tests.helpers.backtests import submit_backtest

VALID_CSV = (
    b"timestamp,open,high,low,close,volume\n"
    b"2024-01-01 09:15:00,100,101,99,100.5,1000\n"
    b"2024-01-01 09:16:00,100.5,102,100,101.5,1200\n"
    b"2024-01-01 09:17:00,101.5,103,101,102.5,900\n"
)


def _execute(
    client: TestClient,
    *,
    strategy_id: str,
    dataset_id: str,
    dataset_version: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "strategy_id": strategy_id,
        "dataset_id": dataset_id,
        "initial_capital": 100_000,
        "commission": 0,
        "slippage": 0,
    }
    if dataset_version is not None:
        payload["dataset_version"] = dataset_version
    return submit_backtest(client, payload)


def test_execute_defaults_to_latest_dataset_version(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    client.post(f"/api/v1/datasets/{dataset_id}/validate")
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)

    body = _execute(client, strategy_id=strategy_id, dataset_id=dataset_id)
    assert body["dataset_version_number"] == 2
    assert body["dataset_fingerprint"]


def test_execute_against_historical_dataset_version(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    client.post(f"/api/v1/datasets/{dataset_id}/validate")
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)

    body = _execute(client, strategy_id=strategy_id, dataset_id=dataset_id, dataset_version=1)
    assert body["dataset_version_number"] == 1

    run = client.get(f"/api/v1/backtests/runs/{body['run_id']}").json()
    assert run["dataset_version_number"] == 1


def test_delete_dataset_blocked_when_referenced(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)
    _execute(client, strategy_id=strategy_id, dataset_id=dataset_id)

    response = client.delete(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "CONFLICT"
    assert "referenced" in body["error"]["message"].lower()
    assert body["error"]["details"]["reference_count"] == 1


def test_delete_dataset_allowed_without_references(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    response = client.delete(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 204
    assert client.get(f"/api/v1/datasets/{dataset_id}").status_code == 404


def test_archive_hides_dataset_from_execution(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)

    archive = client.post(f"/api/v1/datasets/{dataset_id}/archive")
    assert archive.status_code == 200
    assert archive.json()["lifecycle"] == "archived"

    response = client.post(
        "/api/v1/backtests/execute",
        json={
            "strategy_id": strategy_id,
            "dataset_id": dataset_id,
            "initial_capital": 100_000,
            "commission": 0,
            "slippage": 0,
        },
    )
    assert response.status_code == 404


def test_archived_dataset_still_readable_and_replayable(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)
    first = _execute(client, strategy_id=strategy_id, dataset_id=dataset_id)

    client.post(f"/api/v1/datasets/{dataset_id}/archive")
    replay = client.get(f"/api/v1/backtests/runs/{first['run_id']}")
    assert replay.status_code == 200
    assert replay.json()["dataset_version_number"] == 1
