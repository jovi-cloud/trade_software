"""Run comparison API contract tests."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from tests.api.test_run_analytics import BARS_CSV, STRATEGY_PAYLOAD, TRADING_CODE, _submit
from tests.helpers.backtests import submit_backtest

# The same round trip held for fewer bars, so the two runs being compared have
# genuinely different risk-adjusted returns and one of them is the best.
SHORTER_HOLD_CODE = """
class Strategy:
    seen = 0

    def on_bar(self, bar):
        index = self.seen
        self.seen = index + 1
        if index == 2:
            self.ctx.buy(quantity=10)
        elif index == 5:
            self.ctx.close()
"""


def _run_variant(client: TestClient, *, name: str, code: str | None = None) -> dict[str, Any]:
    created = client.post("/api/v1/strategies", json={**STRATEGY_PAYLOAD, "name": name})
    strategy_id = created.json()["id"]
    client.put(
        f"/api/v1/strategies/{strategy_id}/code",
        json={"code": code or TRADING_CODE},
    )
    imported = client.post(
        "/api/v1/datasets/import",
        data={"name": f"{name} data", "symbol": "NIFTY", "exchange": "NSE", "timeframe": "1d"},
        files={"file": ("bars.csv", BARS_CSV, "text/csv")},
    )
    body = submit_backtest(
        client,
        {"strategy_id": strategy_id, "dataset_id": imported.json()["id"]},
    )
    return dict(body)


def test_get_comparison_returns_metric_matrix(client: TestClient) -> None:
    first = _submit(client)
    second = _run_variant(client, name="Variant")

    response = client.get(
        "/api/v1/backtests/runs/compare",
        params={"run_ids": [first["run_id"], second["run_id"]]},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["runs"]) == 2
    assert len(body["metric_rows"]) >= 50
    assert body["equity_overlays"]
    assert body["drawdown_overlays"]
    assert body["monthly_returns_overlays"]


def test_post_comparison_matches_get(client: TestClient) -> None:
    first = _submit(client)
    second = _run_variant(client, name="Variant POST")

    get_response = client.get(
        "/api/v1/backtests/runs/compare",
        params={"run_ids": [first["run_id"], second["run_id"]]},
    )
    post_response = client.post(
        "/api/v1/backtests/runs/compare",
        json={"run_ids": [first["run_id"], second["run_id"]]},
    )

    assert get_response.status_code == 200
    assert post_response.status_code == 200
    assert post_response.json()["metric_rows"] == get_response.json()["metric_rows"]


def test_comparison_highlights_best_metric_using_catalog(client: TestClient) -> None:
    """One run must win. Two runs of the same strategy tie and highlight nothing.

    Asserted unconditionally rather than behind an ``is not None`` guard: that
    guard is what let this test pass while both runs were in fact erroring on
    their first bar and reporting no Sharpe at all.
    """
    first = _submit(client)
    second = _run_variant(client, name="Another", code=SHORTER_HOLD_CODE)

    response = client.post(
        "/api/v1/backtests/runs/compare",
        json={"run_ids": [first["run_id"], second["run_id"]]},
    )
    sharpe = next(row for row in response.json()["metric_rows"] if row["key"] == "sharpe_ratio")
    first_value, second_value = sharpe["values"]
    assert first_value is not None
    assert second_value is not None
    assert first_value != second_value, "the variant must differ or there is no best to highlight"
    assert sharpe["best_run_index"] in {0, 1}


def test_comparison_rejects_single_run(client: TestClient) -> None:
    executed = _submit(client)

    response = client.post(
        "/api/v1/backtests/runs/compare",
        json={"run_ids": [executed["run_id"]]},
    )

    assert response.status_code == 422


def test_comparison_rejects_unknown_run(client: TestClient) -> None:
    executed = _submit(client)

    response = client.post(
        "/api/v1/backtests/runs/compare",
        json={"run_ids": [executed["run_id"], "missing-run-id"]},
    )

    assert response.status_code == 404


def test_comparison_export_shape_is_json_serializable(client: TestClient) -> None:
    first = _submit(client)
    second = _run_variant(client, name="Export")

    response = client.post(
        "/api/v1/backtests/runs/compare",
        json={"run_ids": [first["run_id"], second["run_id"]]},
    )

    assert response.status_code == 200
    json.dumps(response.json())
