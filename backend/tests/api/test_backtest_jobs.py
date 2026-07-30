"""Job cancel and bar-limit behaviour."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from tests.api.test_backtests import _create_strategy, _import_dataset, _save_strategy_code
from tests.helpers.backtests import run_backtest


def test_execute_with_max_bars_replays_only_a_prefix(client: TestClient) -> None:
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)
    dataset_id = _import_dataset(client)

    body = run_backtest(
        client,
        {
            "strategy_id": strategy_id,
            "dataset_id": dataset_id,
            "max_bars": 2,
        },
    )

    assert body["bars_processed"] == 2
    assert len(body["candles"]) == 2


def test_cancel_completed_job_is_harmless(client: TestClient) -> None:
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)
    dataset_id = _import_dataset(client)

    submit = client.post(
        "/api/v1/backtests/execute",
        json={"strategy_id": strategy_id, "dataset_id": dataset_id},
    )
    assert submit.status_code == 202
    job_id = submit.json()["job_id"]

    deadline = time.monotonic() + 30.0
    status = "pending"
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}")
        assert job.status_code == 200
        status = job.json()["status"]
        if status in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.05)
    assert status == "completed"

    cancel = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "completed"
