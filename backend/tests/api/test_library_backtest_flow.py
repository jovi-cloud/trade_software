"""The Strategy Library -> Backtest workflow, end to end over HTTP.

Walks the route a trader actually takes - browse the library, open a strategy,
read its parameter contract, validate an edit, pick a dataset, run, then inspect
the saved result and navigate back - and asserts that each step hands the next
one what it needs. The individual pieces are covered elsewhere; what is tested
here is that they join up.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers.backtests import run_backtest, run_events, submit_backtest

LIBRARY_STRATEGY_ID = "ema_crossover"

#: Fast/slow crossover parameters small enough to signal inside a short fixture,
#: with the trend filter and ATR stops switched off so the only thing that can
#: open or close a position is the crossover itself.
FAST_PARAMS = {
    "fast_period": 2,
    "slow_period": 4,
    "trend_filter_period": 0,
    "atr_period": 2,
    "stop_atr_multiple": 0.0,
    "target_r_multiple": 0.0,
    "trailing_atr_multiple": 0.0,
    "max_bars_in_trade": 0,
    "capital_pct": 50.0,
    "direction": "long_only",
}


def _zigzag_csv() -> bytes:
    """Bars that trend up and down twice.

    Four legs, not two: the second downturn is what crosses the fast EMA back
    under the slow one and closes the position, so the fixture yields a
    completed round trip for the Trade Inspector rather than an open one.
    """
    legs = (
        [100.0 + step for step in range(12)],
        [111.0 - step for step in range(12)],
        [100.0 + step for step in range(12)],
        [111.0 - step for step in range(12)],
    )
    closes = [close for leg in legs for close in leg]

    rows = ["timestamp,open,high,low,close,volume"]
    for index, close in enumerate(closes):
        minute = 15 + index
        stamp = f"2024-01-01 {9 + minute // 60:02d}:{minute % 60:02d}:00"
        rows.append(f"{stamp},{close:.2f},{close + 0.5:.2f},{close - 0.5:.2f},{close:.2f},1000")
    return ("\n".join(rows) + "\n").encode()


def _import_dataset(client: TestClient, name: str = "NIFTY 1m") -> str:
    response = client.post(
        "/api/v1/datasets/import",
        data={"name": name, "symbol": "NIFTY", "exchange": "NSE", "timeframe": "1m"},
        files={"file": ("bars.csv", _zigzag_csv(), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


# ---------------------------------------------------------------------------
# Step 1-3: discover, load the parameter contract, validate an edit
# ---------------------------------------------------------------------------


def test_library_listing_declares_the_explainability_a_run_should_use(client: TestClient) -> None:
    response = client.get("/api/v1/strategy-library", params={"valid_only": True})

    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    for item in items:
        assert item["supports_condition_tracing"] is True
        assert item["recommended_explain_level"] == "full"


def test_detail_carries_everything_the_run_form_needs(client: TestClient) -> None:
    response = client.get(f"/api/v1/strategy-library/{LIBRARY_STRATEGY_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["parameter_groups"]
    assert body["default_params"]
    assert body["recommended_explain_level"] == "full"
    # Every declared parameter has a default, or the generated editor opens blank.
    declared = {spec["name"] for spec in body["parameters"]}
    assert declared == set(body["default_params"])


def test_validate_rejects_an_edit_that_breaks_a_cross_parameter_rule(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/strategy-library/{LIBRARY_STRATEGY_ID}/validate",
        json={"params": {"fast_period": 30, "slow_period": 10}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is False
    assert any(finding["param"] == "fast_period" for finding in body["errors"])


# ---------------------------------------------------------------------------
# Step 4-6: pick a dataset and run, with no research record created by hand
# ---------------------------------------------------------------------------


def test_run_from_library_needs_no_pre_existing_strategy_record(client: TestClient) -> None:
    dataset_id = _import_dataset(client)

    body = submit_backtest(client, {
            "dataset_id": dataset_id,
            "library_strategy_id": LIBRARY_STRATEGY_ID,
            "strategy_params": FAST_PARAMS,
        })
    assert body["completed"] is True
    assert body["run_id"] is not None
    assert body["bars_processed"] == 48

    # A research container was provisioned, named after the library strategy.
    strategies = client.get("/api/v1/strategies").json()["items"]
    assert [item["name"] for item in strategies] == ["EMA Crossover"]


def test_repeat_runs_reuse_the_same_research_container(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    payload = {
        "dataset_id": dataset_id,
        "library_strategy_id": LIBRARY_STRATEGY_ID,
        "strategy_params": FAST_PARAMS,
    }

    first_body = submit_backtest(client, payload)
    second_body = submit_backtest(client, {**payload, "commission": 0.001})
    assert first_body["run_id"] is not None
    assert second_body["run_id"] is not None
    assert client.get("/api/v1/strategies").json()["total"] == 1


def test_container_name_avoids_colliding_with_a_user_strategy(client: TestClient) -> None:
    client.post(
        "/api/v1/strategies",
        json={
            "name": "EMA Crossover",
            "description": "My own take on the idea.",
            "market_type": "equity",
            "instrument": "NIFTY",
            "timeframe": "15m",
            "status": "draft",
            "confidence_level": 5,
            "priority": "medium",
        },
    )
    dataset_id = _import_dataset(client)

    submit_backtest(
        client,
        {
            "dataset_id": dataset_id,
            "library_strategy_id": LIBRARY_STRATEGY_ID,
            "strategy_params": FAST_PARAMS,
        },
    )

    names = {item["name"] for item in client.get("/api/v1/strategies").json()["items"]}
    assert names == {"EMA Crossover", "EMA Crossover (Library 2)"}


def test_run_rejects_parameters_that_fail_validation(client: TestClient) -> None:
    dataset_id = _import_dataset(client)

    response = client.post(
        "/api/v1/backtests/execute",
        json={
            "dataset_id": dataset_id,
            "library_strategy_id": LIBRARY_STRATEGY_ID,
            "strategy_params": {"fast_period": 30, "slow_period": 10},
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    # A rejected request must not leave a container or a run behind.
    assert client.get("/api/v1/strategies").json()["total"] == 0
    assert client.get("/api/v1/backtests/runs").json()["total"] == 0


def test_run_against_a_missing_dataset_creates_no_container(client: TestClient) -> None:
    response = client.post(
        "/api/v1/backtests/execute",
        json={"dataset_id": "missing", "library_strategy_id": LIBRARY_STRATEGY_ID},
    )

    assert response.status_code == 404
    assert client.get("/api/v1/strategies").json()["total"] == 0


def test_run_requires_some_strategy_to_be_named(client: TestClient) -> None:
    dataset_id = _import_dataset(client)

    response = client.post("/api/v1/backtests/execute", json={"dataset_id": dataset_id})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_params_are_rejected_without_a_library_strategy(client: TestClient) -> None:
    dataset_id = _import_dataset(client)

    response = client.post(
        "/api/v1/backtests/execute",
        json={
            "strategy_id": "whatever",
            "dataset_id": dataset_id,
            "strategy_params": {"fast_period": 5},
        },
    )

    assert response.status_code == 422


def test_unknown_library_strategy_returns_404(client: TestClient) -> None:
    dataset_id = _import_dataset(client)

    response = client.post(
        "/api/v1/backtests/execute",
        json={"dataset_id": dataset_id, "library_strategy_id": "no_such_strategy"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Explainability defaults
# ---------------------------------------------------------------------------


def test_library_run_defaults_to_full_explainability(client: TestClient) -> None:
    dataset_id = _import_dataset(client)

    body = submit_backtest(
        client,
        {
            "dataset_id": dataset_id,
            "library_strategy_id": LIBRARY_STRATEGY_ID,
            "strategy_params": FAST_PARAMS,
        },
    )
    assert body["explain_level"] == "full"
    # Decision-layer traces are per-bar, so they are read through the paginated
    # events endpoint rather than inlined on the receipt or the run detail.
    decision_events = run_events(client, body["run_id"], layer="decision")
    assert decision_events


def test_an_explicit_level_still_wins(client: TestClient) -> None:
    dataset_id = _import_dataset(client)

    body = submit_backtest(
        client,
        {
            "dataset_id": dataset_id,
            "library_strategy_id": LIBRARY_STRATEGY_ID,
            "strategy_params": FAST_PARAMS,
            "explain_level": "trades_only",
        },
    )
    assert body["explain_level"] == "trades_only"


def test_user_code_runs_keep_the_old_default(client: TestClient) -> None:
    created = client.post(
        "/api/v1/strategies",
        json={
            "name": "Hand written",
            "description": "Logs each bar.",
            "market_type": "equity",
            "instrument": "NIFTY",
            "timeframe": "1m",
            "status": "draft",
            "confidence_level": 5,
            "priority": "medium",
        },
    )
    strategy_id = str(created.json()["id"])
    client.put(
        f"/api/v1/strategies/{strategy_id}/code",
        json={
            "code": "class Strategy:\n    def on_bar(self, bar):\n        self.ctx.log(bar.ts)\n"
        },
    )
    dataset_id = _import_dataset(client)

    body = submit_backtest(client, {"strategy_id": strategy_id, "dataset_id": dataset_id})
    assert body["explain_level"] == "trades_only"


# ---------------------------------------------------------------------------
# Step 7-10: the saved result, the inspectors, and the way back
# ---------------------------------------------------------------------------


def test_saved_run_pins_the_library_strategy_and_its_parameters(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    body = submit_backtest(client, {
            "dataset_id": dataset_id,
            "library_strategy_id": LIBRARY_STRATEGY_ID,
            "strategy_params": FAST_PARAMS,
        })
    run_id = body["run_id"]

    response = client.get(f"/api/v1/backtests/runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["library_strategy_id"] == LIBRARY_STRATEGY_ID
    assert body["library_strategy_version"] == "1.0.0"
    assert body["strategy_name"] == "EMA Crossover"
    # Resolved values, not just the ones that were sent: this is what "run again"
    # reloads into the editor.
    assert body["strategy_params"]["fast_period"] == 2
    assert set(body["strategy_params"]) >= set(FAST_PARAMS)
    assert body["strategy_code_snapshot"].startswith("# Strategy Library: ema_crossover@1.0.0")


def test_run_list_flags_library_runs_for_the_back_link(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    submit_backtest(
        client,
        {
            "dataset_id": dataset_id,
            "library_strategy_id": LIBRARY_STRATEGY_ID,
            "strategy_params": FAST_PARAMS,
        },
    )

    response = client.get("/api/v1/backtests/runs")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["library_strategy_id"] == LIBRARY_STRATEGY_ID


def test_library_run_produces_trades_the_inspectors_can_explain(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    body = run_backtest(
        client,
        {
            "dataset_id": dataset_id,
            "library_strategy_id": LIBRARY_STRATEGY_ID,
            "strategy_params": FAST_PARAMS,
        },
    )
    run_id = body["id"]
    assert body["trade_count"] >= 1, "fixture must produce a trade for the inspectors to explain"

    trade = client.get(f"/api/v1/backtests/runs/{run_id}/trades/1")
    assert trade.status_code == 200, trade.text

    bar_index = body["orders"][0]["submitted_bar_index"]
    bar = client.get(f"/api/v1/backtests/runs/{run_id}/bars/{bar_index}")
    assert bar.status_code == 200, bar.text
    assert bar.json()["conditions"], "a library strategy must trace its conditions"


def test_returning_to_the_container_lists_only_its_own_runs(client: TestClient) -> None:
    dataset_id = _import_dataset(client)
    body = submit_backtest(
        client,
        {
            "dataset_id": dataset_id,
            "library_strategy_id": LIBRARY_STRATEGY_ID,
            "strategy_params": FAST_PARAMS,
        },
    )
    strategy_id = client.get(f"/api/v1/backtests/runs/{body['run_id']}").json()["strategy_id"]

    response = client.get("/api/v1/backtests/runs", params={"strategy_id": strategy_id})

    assert response.status_code == 200
    assert response.json()["total"] == 1
