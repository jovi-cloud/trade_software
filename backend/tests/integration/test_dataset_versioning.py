"""Tests for immutable dataset versioning and lineage."""

from __future__ import annotations

import polars as pl
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.hashing import hash_file
from app.core.paths import get_data_paths
from app.data.fingerprint import compute_dataset_fingerprint
from app.domain.enums import Timeframe
from app.repositories.dataset_version_repo import DatasetVersionRepository
from app.services.import_service import ImportService

VALID_CSV = (
    b"timestamp,open,high,low,close,volume\n"
    b"2024-01-01 09:15:00,100,101,99,100.5,1000\n"
    b"2024-01-01 09:16:00,100.5,102,100,101.5,1200\n"
    b"2024-01-01 09:17:00,101.5,103,101,102.5,900\n"
)

ALT_CSV_SAME_BARS = (
    b"Date,Open,High,Low,Close,Vol\n"
    b"2024-01-01 09:15:00,100,101,99,100.5,1000\n"
    b"2024-01-01 09:16:00,100.5,102,100,101.5,1200\n"
    b"2024-01-01 09:17:00,101.5,103,101,102.5,900\n"
)


def _service(session: Session, settings: Settings) -> ImportService:
    return ImportService(session, get_data_paths(settings))


def test_fingerprint_is_deterministic_for_identical_cleaned_bars() -> None:
    bars = pl.DataFrame(
        {
            "ts": [1_704_093_300_000, 1_704_093_360_000],
            "open": [100.0, 100.5],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000.0, 1200.0],
        }
    )
    first = compute_dataset_fingerprint(bars, timeframe="1m", timezone="UTC")
    second = compute_dataset_fingerprint(bars, timeframe="1m", timezone="UTC")
    assert first == second


def test_fingerprint_matches_for_different_source_files_with_same_bars(
    db_session: Session, settings: Settings
) -> None:
    service = _service(db_session, settings)
    first = service.import_csv(
        name="A", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=VALID_CSV
    )
    service.import_new_version(
        first.id,
        content=ALT_CSV_SAME_BARS,
        filename="alt.csv",
    )
    versions = DatasetVersionRepository(db_session).list_for_dataset(first.id)
    assert len(versions) == 2
    assert versions[0].fingerprint == versions[1].fingerprint


def test_reimport_creates_new_version_without_overwriting_parquet(
    db_session: Session, settings: Settings
) -> None:
    service = _service(db_session, settings)
    paths = get_data_paths(settings)
    dataset = service.import_csv(
        name="NIFTY 1m", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=VALID_CSV
    )

    v1_path = paths.dataset_version_parquet(dataset.id, 1)
    v1_hash = hash_file(v1_path)

    service.revalidate(dataset.id)

    v2_path = paths.dataset_version_parquet(dataset.id, 2)
    assert v1_path.exists()
    assert v2_path.exists()
    assert hash_file(v1_path) == v1_hash
    assert dataset.current_version_number == 2


def test_list_versions_endpoint(client: TestClient) -> None:
    created = client.post(
        "/api/v1/datasets/import",
        data={"name": "NIFTY", "symbol": "NIFTY", "exchange": "NSE", "timeframe": "1m"},
        files={"file": ("bars.csv", VALID_CSV, "text/csv")},
    ).json()

    client.post(
        f"/api/v1/datasets/{created['id']}/validate",
    )

    response = client.get(f"/api/v1/datasets/{created['id']}/versions")
    assert response.status_code == 200
    versions = response.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[1]["version_number"] == 1
    assert versions[0]["fingerprint"]


def test_backtest_run_records_dataset_lineage(client: TestClient) -> None:
    from tests.api.test_backtests import _create_strategy, _import_dataset, _save_strategy_code

    dataset_id = _import_dataset(client)
    strategy_id = _create_strategy(client)
    _save_strategy_code(client, strategy_id)

    run = client.post(
        "/api/v1/backtests/execute",
        json={
            "strategy_id": strategy_id,
            "dataset_id": dataset_id,
            "initial_capital": 100000,
            "commission": 0,
            "slippage": 0,
        },
    ).json()

    detail = client.get(f"/api/v1/backtests/runs/{run['run_id']}").json()
    assert detail["dataset_version_id"]
    assert detail["dataset_version_number"] == 1
    assert detail["dataset_import_id"]
    assert detail["dataset_imported_at"]
    assert detail["dataset_quality_score"] is not None
    assert detail["dataset_hash"]

    client.post(f"/api/v1/datasets/{dataset_id}/validate")
    second_run = client.post(
        "/api/v1/backtests/execute",
        json={
            "strategy_id": strategy_id,
            "dataset_id": dataset_id,
            "initial_capital": 100000,
            "commission": 0,
            "slippage": 0,
        },
    ).json()
    second_detail = client.get(f"/api/v1/backtests/runs/{second_run['run_id']}").json()
    assert second_detail["dataset_version_number"] == 2
    assert detail["dataset_version_number"] == 1
