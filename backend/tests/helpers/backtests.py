"""Helpers for backtest API tests."""

from __future__ import annotations

import time
from typing import Any

from fastapi.testclient import TestClient


def submit_backtest(
    client: TestClient,
    payload: dict[str, Any],
    *,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Submit a backtest job and poll until it finishes.

    Returns the job *receipt* - ``run_id`` plus headline counts. For the replay
    itself (candles, trades, orders, analytics) use :func:`run_backtest`, which
    reads the persisted run the way the frontend does.
    """
    response = client.post("/api/v1/backtests/execute", json=payload)
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}")
        assert job.status_code == 200, job.text
        body = job.json()
        status = body["status"]
        if status == "completed":
            assert body["result"] is not None
            result: dict[str, Any] = body["result"]
            return result
        if status == "failed":
            raise AssertionError(body.get("error_message") or "Backtest job failed")
        time.sleep(0.05)

    raise TimeoutError(f"Backtest job {job_id} did not finish within {timeout_s}s")


def run_backtest(
    client: TestClient,
    payload: dict[str, Any],
    *,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Run a backtest and return the persisted run detail.

    The path the frontend takes: submit, poll to completion, then read the run
    by the id on the receipt.
    """
    receipt = submit_backtest(client, payload, timeout_s=timeout_s)
    response = client.get(f"/api/v1/backtests/runs/{receipt['run_id']}")
    assert response.status_code == 200, response.text
    detail: dict[str, Any] = response.json()
    return detail


def run_events(
    client: TestClient,
    run_id: str,
    *,
    limit: int = 200,
    **filters: Any,
) -> list[dict[str, Any]]:
    """The run's explainability events, through the paginated endpoint."""
    response = client.get(
        f"/api/v1/backtests/runs/{run_id}/events",
        params={"limit": limit, **filters},
    )
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items
