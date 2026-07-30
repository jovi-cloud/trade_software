"""Regression tests for library container creation races."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from tests.api.test_library_backtest_flow import FAST_PARAMS, LIBRARY_STRATEGY_ID, _import_dataset
from tests.helpers.backtests import submit_backtest


def test_parallel_library_runs_create_one_container(client: TestClient) -> None:
    """Concurrent first-time library runs must not insert duplicate containers."""
    dataset_id = _import_dataset(client)
    payload = {
        "dataset_id": dataset_id,
        "library_strategy_id": LIBRARY_STRATEGY_ID,
        "strategy_params": FAST_PARAMS,
    }

    def run_once() -> None:
        submit_backtest(client, payload)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: run_once(), range(3)))

    assert client.get("/api/v1/strategies").json()["total"] == 1
