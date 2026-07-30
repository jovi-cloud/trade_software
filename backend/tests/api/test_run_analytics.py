"""Analytics on the run endpoints - contract, persistence and back-compat.

The analytics module extends the existing endpoints rather than adding parallel
ones, so these tests assert on ``/backtests/execute`` and ``/backtests/runs``.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.helpers.backtests import run_backtest, submit_backtest

STRATEGY_PAYLOAD = {
    "name": "Buy And Hold",
    "description": "Enters on the first bar and holds.",
    "market_type": "equity",
    "instrument": "NIFTY",
    "timeframe": "1d",
    "status": "draft",
    "confidence_level": 5,
    "priority": "medium",
}

# Ten consecutive daily bars, so one bar is one trading day and the daily,
# monthly and yearly series are all exercised without a data gap.
BARS_CSV = (
    b"timestamp,open,high,low,close,volume\n"
    b"2024-01-01 00:00:00,100,102,99,101,1000\n"
    b"2024-01-02 00:00:00,101,104,100,103,1200\n"
    b"2024-01-03 00:00:00,103,105,101,102,900\n"
    b"2024-01-04 00:00:00,102,106,100,105,1100\n"
    b"2024-01-05 00:00:00,105,107,103,106,1300\n"
    b"2024-01-06 00:00:00,106,108,104,107,1000\n"
    b"2024-01-07 00:00:00,107,109,105,106,1200\n"
    b"2024-01-08 00:00:00,106,110,105,109,900\n"
    b"2024-01-09 00:00:00,109,111,107,110,1100\n"
    b"2024-01-10 00:00:00,110,112,108,111,1300\n"
)

# Buys on the second bar and closes near the end, producing one round trip.
#
# The bar counter is a class attribute rather than ``getattr(self, "seen", 0)``:
# the strategy sandbox allows ``hasattr`` but deliberately not ``getattr``, so
# the getattr form raised NameError on the first bar and this fixture never
# actually traded.
TRADING_CODE = """
class Strategy:
    seen = 0

    def on_bar(self, bar):
        index = self.seen
        self.seen = index + 1
        if index == 1:
            self.ctx.buy(quantity=10)
        elif index == 7:
            self.ctx.close()
"""


def _payload(client: TestClient) -> dict[str, Any]:
    """A strategy and dataset ready to run, as an execute request."""
    created = client.post("/api/v1/strategies", json=STRATEGY_PAYLOAD)
    assert created.status_code == 201
    strategy_id = created.json()["id"]

    saved = client.put(f"/api/v1/strategies/{strategy_id}/code", json={"code": TRADING_CODE})
    assert saved.status_code == 200

    imported = client.post(
        "/api/v1/datasets/import",
        data={"name": "NIFTY 1d", "symbol": "NIFTY", "exchange": "NSE", "timeframe": "1d"},
        files={"file": ("bars.csv", BARS_CSV, "text/csv")},
    )
    assert imported.status_code == 201

    return {
        "strategy_id": strategy_id,
        "dataset_id": imported.json()["id"],
        "initial_capital": 100_000,
    }


def _submit(client: TestClient) -> dict[str, Any]:
    """Run and return the job receipt only."""
    return submit_backtest(client, _payload(client))


def _run_backtest(client: TestClient) -> dict[str, Any]:
    """Run and return the persisted run detail."""
    return run_backtest(client, _payload(client))


def test_execute_returns_a_full_analytics_report(client: TestClient) -> None:
    body = _run_backtest(client)
    analytics = body["analytics"]

    assert set(analytics) == {
        "returns",
        "risk",
        "risk_adjusted",
        "trades",
        "portfolio",
        "statistics",
        "series",
        "meta",
        "metrics",
    }
    assert analytics["meta"]["bar_count"] == 10
    assert analytics["meta"]["initial_capital"] == 100_000
    assert analytics["meta"]["analytics_version"]


def test_every_metric_carries_its_display_metadata(client: TestClient) -> None:
    """What makes the frontend tooltips and Run Comparison possible."""
    metrics = _run_backtest(client)["analytics"]["metrics"]

    assert len(metrics) >= 50
    for metric in metrics:
        assert metric["key"]
        assert metric["label"]
        assert metric["description"]
        assert metric["category"] in {
            "returns",
            "risk",
            "risk_adjusted",
            "trades",
            "portfolio",
            "statistics",
        }
        assert metric["format"] in {
            "currency",
            "percent",
            "ratio",
            "integer",
            "duration",
            "number",
        }


def test_the_report_carries_every_series_the_result_page_needs(client: TestClient) -> None:
    series = _run_backtest(client)["analytics"]["series"]

    assert len(series["equity_curve"]) == 10
    assert len(series["drawdown_curve"]) == 10
    assert len(series["daily_pnl"]) == 10
    assert len(series["monthly_returns"]) == 1
    assert len(series["yearly_returns"]) == 1
    assert series["curves_downsampled"] is False
    assert series["monthly_returns"][0]["year"] == 2024
    assert series["monthly_returns"][0]["month"] == 1


def test_the_report_is_persisted_and_returned_by_the_run_endpoint(client: TestClient) -> None:
    """The report computed during execution survives on the run record.

    The job receipt carries only ``run_id``, so the run endpoint is the only
    place the report can come from - which is exactly what this asserts.
    """
    receipt = _submit(client)

    response = client.get(f"/api/v1/backtests/runs/{receipt['run_id']}")

    assert response.status_code == 200
    stored = response.json()["analytics"]
    assert stored["meta"]["bar_count"] == 10
    assert stored["meta"]["initial_capital"] == 100_000
    assert stored["returns"]["total_return_pct"] is not None
    assert len(stored["series"]["equity_curve"]) == 10


def test_headline_metrics_are_exposed_on_the_runs_list(client: TestClient) -> None:
    executed = _run_backtest(client)

    response = client.get("/api/v1/backtests/runs")

    assert response.status_code == 200
    item = next(row for row in response.json()["items"] if row["id"] == executed["id"])
    assert item["total_return_pct"] == executed["analytics"]["returns"]["total_return_pct"]
    assert item["max_drawdown_pct"] == executed["analytics"]["risk"]["max_drawdown_pct"]
    assert item["exposure_pct"] == executed["analytics"]["risk"]["exposure_pct"]


def test_runs_can_be_sorted_by_an_analytics_metric(client: TestClient) -> None:
    _run_backtest(client)

    response = client.get("/api/v1/backtests/runs", params={"sort": "sharpe", "order": "desc"})

    assert response.status_code == 200


def test_an_unknown_sort_column_is_still_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/backtests/runs", params={"sort": "nonsense"})

    assert response.status_code == 422


def test_a_run_saved_without_analytics_is_rebuilt_on_read(
    client: TestClient, db_engine: Engine
) -> None:
    """Back-compat: runs recorded before this module existed must still open.

    The report is rebuilt from the trades and candles that run already stored,
    then cached back onto the row so the runs list can sort on it afterwards.
    """
    executed = _run_backtest(client)
    run_id = executed["id"]

    with db_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE backtest_runs SET analytics_json = NULL, sharpe = NULL, "
                "total_return_pct = NULL WHERE id = :id"
            ),
            {"id": run_id},
        )

    response = client.get(f"/api/v1/backtests/runs/{run_id}")

    assert response.status_code == 200
    rebuilt = response.json()["analytics"]
    assert rebuilt["returns"] == executed["analytics"]["returns"]
    assert rebuilt["risk"] == executed["analytics"]["risk"]

    with db_engine.begin() as connection:
        row = connection.execute(
            text("SELECT analytics_json, total_return_pct FROM backtest_runs WHERE id = :id"),
            {"id": run_id},
        ).one()
    assert row[0] is not None
    assert row[1] == executed["analytics"]["returns"]["total_return_pct"]


def test_a_stored_report_from_an_older_schema_is_rebuilt_not_fatal(
    client: TestClient, db_engine: Engine
) -> None:
    executed = _run_backtest(client)
    run_id = executed["id"]

    with db_engine.begin() as connection:
        connection.execute(
            text("UPDATE backtest_runs SET analytics_json = :payload WHERE id = :id"),
            {"payload": json.dumps({"returns": {"net_profit": 1.0}}), "id": run_id},
        )

    response = client.get(f"/api/v1/backtests/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["analytics"]["returns"] == executed["analytics"]["returns"]


def test_a_run_with_no_trades_still_returns_a_report(client: TestClient) -> None:
    created = client.post("/api/v1/strategies", json={**STRATEGY_PAYLOAD, "name": "Does Nothing"})
    strategy_id = created.json()["id"]
    client.put(
        f"/api/v1/strategies/{strategy_id}/code",
        json={"code": "class Strategy:\n    def on_bar(self, bar):\n        pass\n"},
    )
    imported = client.post(
        "/api/v1/datasets/import",
        data={"name": "NIFTY flat", "symbol": "NIFTY", "exchange": "NSE", "timeframe": "1d"},
        files={"file": ("bars.csv", BARS_CSV, "text/csv")},
    )

    body = run_backtest(
        client,
        {"strategy_id": strategy_id, "dataset_id": imported.json()["id"]},
    )

    analytics = body["analytics"]
    assert analytics["trades"]["total_trades"] == 0
    assert analytics["returns"]["net_profit"] == 0.0
    assert analytics["returns"]["profit_factor"] is None
    assert analytics["risk_adjusted"]["sharpe_ratio"] is None
    # The equity curve still exists: flat, one point per bar.
    assert len(analytics["series"]["equity_curve"]) == 10
