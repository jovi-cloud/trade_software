"""ExecutionService against a real temp SQLite file + parquet bars."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.paths import get_data_paths
from app.domain.enums import Timeframe
from app.services.execution_service import ExecutionService
from app.services.import_service import ImportService

VALID_CSV = (
    b"timestamp,open,high,low,close,volume\n"
    b"2024-01-01 09:15:00,100,101,99,100.5,1000\n"
    b"2024-01-01 09:16:00,100.5,102,100,101.5,1200\n"
)

STRATEGY_CODE = """
class Strategy:
    def on_bar(self, bar):
        self.ctx.log(bar.ts)
"""


def _service(session: Session, settings: Settings) -> ExecutionService:
    return ExecutionService(session, get_data_paths(settings))


def _create_strategy_with_code(client: TestClient) -> str:
    created = client.post(
        "/api/v1/strategies",
        json={
            "name": "Replay Test",
            "description": "Counts bars during replay.",
            "market_type": "equity",
            "instrument": "NIFTY",
            "timeframe": "1m",
            "status": "draft",
            "confidence_level": 5,
            "priority": "medium",
        },
    )
    strategy_id = str(created.json()["id"])
    client.put(f"/api/v1/strategies/{strategy_id}/code", json={"code": STRATEGY_CODE})
    return strategy_id


def test_execute_replays_imported_dataset(
    db_session: Session, settings: Settings, client: TestClient
) -> None:
    strategy_id = _create_strategy_with_code(client)
    dataset = ImportService(db_session, get_data_paths(settings)).import_csv(
        name="NIFTY 1m", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=VALID_CSV
    )

    result = _service(db_session, settings).execute(
        strategy_id=strategy_id,
        dataset_id=dataset.id,
        config=ExecutionService.build_config(initial_capital=50_000, commission=0, slippage=0),
    )

    assert result.completed is True
    assert result.bars_processed == 2
    assert len(result.strategy_logs) == 2


def test_execute_rejects_missing_strategy(db_session: Session, settings: Settings) -> None:
    dataset = ImportService(db_session, get_data_paths(settings)).import_csv(
        name="NIFTY 1m", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=VALID_CSV
    )

    with pytest.raises(NotFoundError):
        _service(db_session, settings).execute(
            strategy_id="missing",
            dataset_id=dataset.id,
            config=ExecutionService.build_config(initial_capital=100_000, commission=0, slippage=0),
        )


def test_execute_rejects_strategy_without_code(
    db_session: Session, settings: Settings, client: TestClient
) -> None:
    created = client.post(
        "/api/v1/strategies",
        json={
            "name": "No Code",
            "description": "Has no saved code yet.",
            "market_type": "equity",
            "instrument": "NIFTY",
            "timeframe": "1m",
            "status": "draft",
            "confidence_level": 5,
            "priority": "medium",
        },
    )
    strategy_id = str(created.json()["id"])
    dataset = ImportService(db_session, get_data_paths(settings)).import_csv(
        name="NIFTY 1m", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=VALID_CSV
    )

    with pytest.raises(ValidationError, match="no code"):
        _service(db_session, settings).execute(
            strategy_id=strategy_id,
            dataset_id=dataset.id,
            config=ExecutionService.build_config(initial_capital=100_000, commission=0, slippage=0),
        )
