"""Backtest run persistence API contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.test_backtests import (
    STRATEGY_PAYLOAD,
    _create_strategy,
    _import_dataset,
    _save_strategy_code,
)
from tests.helpers.backtests import submit_backtest


def _execute_backtest(client: TestClient) -> tuple[str, str]:
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)
    dataset_id = _import_dataset(client)

    body = submit_backtest(
        client,
        {
            "strategy_id": strategy_id,
            "dataset_id": dataset_id,
            "initial_capital": 100_000,
            "commission": 0.001,
            "slippage": 0.0005,
        },
    )
    run_id = body["run_id"]
    assert run_id is not None
    return run_id, strategy_id


def test_execute_persists_backtest_run(client: TestClient) -> None:
    run_id, _ = _execute_backtest(client)

    response = client.get(f"/api/v1/backtests/runs/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == run_id
    assert body["status"] == "completed"
    assert body["bars_processed"] == 3
    assert body["trade_count"] == 0
    assert body["strategy_code_snapshot"].strip().startswith("class Strategy")
    assert body["dataset_hash"]
    assert body["strategy_hash"]
    assert body["metrics"]["total_trades"] == 0
    assert len(body["candles"]) == 3
    assert body["research_completion_pct"] == 0
    assert body["research_timeline"]["run_created"] is True


def test_list_backtest_runs(client: TestClient) -> None:
    run_id, strategy_id = _execute_backtest(client)

    response = client.get("/api/v1/backtests/runs", params={"strategy_id": strategy_id})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == run_id
    assert body["items"][0]["strategy_name"] == STRATEGY_PAYLOAD["name"]
    assert body["items"][0]["status"] == "completed"


def test_update_backtest_run_research(client: TestClient) -> None:
    run_id, _ = _execute_backtest(client)

    response = client.patch(
        f"/api/v1/backtests/runs/{run_id}",
        json={
            "experiment_name": "ORB baseline",
            "hypothesis": "First-hour breakouts have edge on NIFTY 1m",
            "what_changed": "Initial baseline with no filters",
            "expected_result": "Positive expectancy after costs",
            "actual_result": "Flat P&L, 0 trades on short sample",
            "conclusion": "Need more data and a real entry rule",
            "next_experiment": "Add volume filter and longer dataset",
            "tags": "orb, baseline, intraday",
            "rating": 3,
            "notes": "Short sample only.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["experiment_name"] == "ORB baseline"
    assert body["hypothesis"].startswith("First-hour")
    assert body["tags"] == "orb, baseline, intraday"
    assert body["rating"] == 3
    assert body["research_completion_pct"] == 100
    assert body["research_timeline"]["run_created"] is True
    assert body["research_timeline"]["research_completed"] is True
    assert body["research_timeline"]["conclusion_written"] is True


def test_list_backtest_runs_search_by_experiment_name(client: TestClient) -> None:
    run_id, _ = _execute_backtest(client)
    client.patch(
        f"/api/v1/backtests/runs/{run_id}",
        json={"experiment_name": "Unique Experiment Alpha"},
    )

    response = client.get("/api/v1/backtests/runs", params={"q": "Unique Experiment"})
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == run_id


def test_list_backtest_runs_search_by_tags(client: TestClient) -> None:
    run_id, _ = _execute_backtest(client)
    client.patch(
        f"/api/v1/backtests/runs/{run_id}",
        json={"tags": "mean-reversion, nifty"},
    )

    response = client.get("/api/v1/backtests/runs", params={"q": "mean-reversion"})
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_backtest_run_notes(client: TestClient) -> None:
    run_id, _ = _execute_backtest(client)

    response = client.patch(
        f"/api/v1/backtests/runs/{run_id}",
        json={"notes": "Looked promising on the opening range."},
    )
    assert response.status_code == 200
    assert response.json()["notes"] == "Looked promising on the opening range."
    assert response.json()["research_completion_pct"] == 0


def test_delete_backtest_run(client: TestClient) -> None:
    run_id, _ = _execute_backtest(client)

    response = client.delete(f"/api/v1/backtests/runs/{run_id}")
    assert response.status_code == 204

    response = client.get(f"/api/v1/backtests/runs/{run_id}")
    assert response.status_code == 404


def test_download_backtest_run_export(client: TestClient) -> None:
    import io
    import zipfile

    run_id, _ = _execute_backtest(client)

    response = client.get(f"/api/v1/backtests/runs/{run_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert "README.txt" in names
        assert "run.json" in names
        assert "candles.csv" in names
        assert "equity_curve.csv" in names
        assert "trades.csv" in names
        assert "strategy_code.py" in names


def test_list_backtest_runs_filter_by_status(client: TestClient) -> None:
    _execute_backtest(client)

    response = client.get("/api/v1/backtests/runs", params={"status": "completed"})
    assert response.status_code == 200
    assert response.json()["total"] >= 1

    response = client.get("/api/v1/backtests/runs", params={"status": "failed"})
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_failed_execution_persists_failed_run(client: TestClient) -> None:
    strategy_id = _create_strategy(client)
    _save_strategy_code(
        client,
        strategy_id,
        code="""
class Strategy:
    def on_bar(self, bar):
        raise RuntimeError("boom")
""",
    )
    dataset_id = _import_dataset(client)

    body = submit_backtest(client, {"strategy_id": strategy_id, "dataset_id": dataset_id})
    assert body["completed"] is False
    run_id = body["run_id"]
    assert run_id is not None

    response = client.get(f"/api/v1/backtests/runs/{run_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_message"]


def test_get_missing_backtest_run_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/backtests/runs/missing")
    assert response.status_code == 404
