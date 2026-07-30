"""The decision log over HTTP: every bar, every verdict, every operand.

The regression these guard is the one that made a real run unexplainable. A
194,553-bar ``ema_crossover`` run reported 0 trades and 0.0% return with no error
and no warning. The cause was 3,707 valid entry signals whose position size
floored to zero - visible nowhere, because the log recorded that the size *was*
zero and not the arithmetic that made it zero, and stopped entirely at bar 50,000.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.test_library_backtest_flow import (
    FAST_PARAMS,
    LIBRARY_STRATEGY_ID,
    _import_dataset,
)
from tests.helpers.backtests import submit_backtest


def _run(client: TestClient, **overrides: object) -> str:
    payload: dict[str, object] = {
        "dataset_id": _import_dataset(client),
        "library_strategy_id": LIBRARY_STRATEGY_ID,
        "strategy_params": FAST_PARAMS,
        "initial_capital": 100_000,
        "explain_level": "full",
    }
    payload.update(overrides)
    body = submit_backtest(client, payload)
    return str(body["run_id"])


def test_a_full_run_records_a_decision_log_for_every_bar(client: TestClient) -> None:
    run_id = _run(client)

    run = client.get(f"/api/v1/backtests/runs/{run_id}").json()
    assert run["decision_log_rows"] == run["bars_processed"]
    assert run["decision_log_rows"] > 0

    response = client.get(f"/api/v1/backtests/runs/{run_id}/decisions")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_rows"] == run["bars_processed"]
    assert body["start"] == 0
    assert body["rows"]
    assert body["log_schema"]["conditions"]
    assert body["log_schema"]["indicators"]


def test_each_row_carries_indicators_conditions_and_operands(client: TestClient) -> None:
    run_id = _run(client)

    body = client.get(
        f"/api/v1/backtests/runs/{run_id}/decisions",
        params={"start": 0, "count": 50},
    ).json()

    rows = body["rows"]
    assert [row["bar_index"] for row in rows] == list(range(len(rows)))
    # OHLCV is on every row, warmup included: the bar happened regardless of
    # whether any rule ran on it.
    assert all(row["close"] > 0 for row in rows)
    # Past warmup the indicators and the sizing operands are populated.
    warm = [row for row in rows if row["indicators"]]
    assert warm, "no bar published an indicator value"
    assert "ema_fast" in warm[-1]["indicators"]
    assert any(row["operands"] for row in rows)
    cash_operands = [
        operand for row in rows for operand in row["operands"] if operand["name"] == "cash"
    ]
    assert cash_operands and cash_operands[0]["label"] == "Cash"


def test_a_window_can_be_paged_through(client: TestClient) -> None:
    run_id = _run(client)
    total = client.get(f"/api/v1/backtests/runs/{run_id}/decisions").json()["total_rows"]

    second = client.get(
        f"/api/v1/backtests/runs/{run_id}/decisions",
        params={"start": 5, "count": 3},
    ).json()

    assert second["total_rows"] == total
    assert second["start"] == 5
    assert [row["bar_index"] for row in second["rows"]] == [5, 6, 7]


def test_an_oversized_window_is_rejected(client: TestClient) -> None:
    run_id = _run(client)

    response = client.get(
        f"/api/v1/backtests/runs/{run_id}/decisions",
        params={"count": 10_000},
    )

    assert response.status_code == 422


def test_the_summary_tallies_every_condition_over_the_whole_run(client: TestClient) -> None:
    run_id = _run(client)

    response = client.get(f"/api/v1/backtests/runs/{run_id}/decisions/summary")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_rows"] > 0
    names = {item["name"] for item in body["conditions"]}
    assert "Entry Rules Met" in names
    for item in body["conditions"]:
        assert item["evaluated"] >= item["passed"]
        assert item["expected"]


def test_a_floored_position_size_is_attributable_from_the_log(client: TestClient) -> None:
    """The user's bug: signals fire, sizes floor to zero, result reads as nothing.

    The fixture trades around 105, so 150 of capital at 50% sizes 0.71 units and
    whole-unit flooring erases it - the same shape as 20% of 1,000 on a share at
    995. The log has to show *why*: the condition failed, and the operands beside
    it show the size that was requested before flooring.
    """
    run_id = _run(client, initial_capital=150)

    run = client.get(f"/api/v1/backtests/runs/{run_id}").json()
    summary = client.get(f"/api/v1/backtests/runs/{run_id}/decisions/summary").json()
    tallies = {item["name"]: item for item in summary["conditions"]}

    # Entries were reached and permitted, and sizing killed all of them.
    assert run["trade_count"] == 0
    assert tallies["Entry Rules Met"]["passed"] > 0
    assert tallies["Position Size Available"]["evaluated"] > 0
    assert tallies["Position Size Available"]["passed"] == 0

    # Find such a bar and confirm the arithmetic is recoverable from it.
    total = summary["total_rows"]
    found = None
    for start in range(0, total, 500):
        page = client.get(
            f"/api/v1/backtests/runs/{run_id}/decisions",
            params={"start": start, "count": 500},
        ).json()
        for row in page["rows"]:
            if row["conditions"].get("Position Size Available") is False:
                found = row
                break
        if found is not None:
            break

    assert found is not None, "no bar recorded a failed position size"
    operands = {item["name"]: item["value"] for item in found["operands"]}
    assert operands["size_capital"] == 150
    assert operands["size_price"] > 0
    # The whole point: a size was genuinely requested, then floored away.
    assert 0 < operands["size_raw_quantity"] < 1
    assert operands["size_quantity"] == 0


def test_an_unevaluated_condition_is_distinguishable_from_a_failed_one(
    client: TestClient,
) -> None:
    """``entry_signal`` is never called while a position is open."""
    run_id = _run(client)
    total = client.get(f"/api/v1/backtests/runs/{run_id}/decisions").json()["total_rows"]

    seen: set[bool | None] = set()
    for start in range(0, total, 500):
        page = client.get(
            f"/api/v1/backtests/runs/{run_id}/decisions",
            params={"start": start, "count": 500},
        ).json()
        for row in page["rows"]:
            seen.add(row["conditions"].get("Entry Rules Met"))

    # Bars where the rule passed, failed, and was never reached at all.
    assert None in seen
    assert False in seen


def test_the_bar_inspector_serves_operands_from_the_log(client: TestClient) -> None:
    run_id = _run(client)

    response = client.get(f"/api/v1/backtests/runs/{run_id}/bars/5")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["conditions"], "conditions must survive the move to the decision log"
    assert {item["name"] for item in body["operands"]}
    assert all("expected_value" in item for item in body["conditions"])


def test_a_trades_only_run_has_no_decision_log(client: TestClient) -> None:
    run_id = _run(client, explain_level="trades_only")

    run = client.get(f"/api/v1/backtests/runs/{run_id}").json()
    assert run["decision_log_rows"] == 0

    response = client.get(f"/api/v1/backtests/runs/{run_id}/decisions")
    assert response.status_code == 404
