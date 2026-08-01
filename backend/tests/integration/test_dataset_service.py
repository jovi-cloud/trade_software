"""DatasetService against a real temp SQLite file + real temp data dir (ARCHITECTURE.md 9)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.paths import get_data_paths
from app.domain.enums import Timeframe
from app.models.dataset import Dataset
from app.services.dataset_service import DatasetService
from app.services.import_service import ImportService

VALID_CSV = (
    b"timestamp,open,high,low,close,volume\n"
    b"2024-01-01 09:15:00,100,101,99,100.5,1000\n"
    b"2024-01-01 09:16:00,100.5,102,100,101.5,1200\n"
)


def _import(session: Session, settings: Settings, **overrides: str) -> Dataset:
    service = ImportService(session, get_data_paths(settings))
    defaults = {"name": "NIFTY 1m", "symbol": "NIFTY", "exchange": "NSE"}
    defaults.update(overrides)
    return service.import_csv(timeframe=Timeframe.M1, content=VALID_CSV, **defaults)


def test_get_missing_dataset_raises_not_found(db_session: Session, settings: Settings) -> None:
    service = DatasetService(db_session, get_data_paths(settings))

    with pytest.raises(NotFoundError):
        service.get("does-not-exist")


def test_list_supports_search_by_name_and_symbol(db_session: Session, settings: Settings) -> None:
    _import(db_session, settings, name="NIFTY 1m", symbol="NIFTY")
    _import(db_session, settings, name="BTC 1m", symbol="BTCUSD")
    service = DatasetService(db_session, get_data_paths(settings))

    items, total = service.list_datasets(
        q="btc", timeframe=None, sort="updated_at", order="desc", limit=20, offset=0
    )

    assert total == 1
    assert items[0].symbol == "BTCUSD"


def test_list_filters_by_timeframe(db_session: Session, settings: Settings) -> None:
    _import(db_session, settings)
    service = DatasetService(db_session, get_data_paths(settings))

    items, total = service.list_datasets(
        q=None, timeframe=Timeframe.M5, sort="updated_at", order="desc", limit=20, offset=0
    )

    assert total == 0
    assert items == []


def test_delete_soft_deletes_and_removes_files(db_session: Session, settings: Settings) -> None:
    paths = get_data_paths(settings)
    dataset = _import(db_session, settings)
    parquet_path = paths.root / dataset.file_path
    import_files = list(paths.imports.glob(f"{dataset.id}_v1.*"))
    assert parquet_path.exists()
    assert import_files

    service = DatasetService(db_session, paths)
    service.delete(dataset.id)

    assert not parquet_path.exists()
    assert not list(paths.imports.glob(f"{dataset.id}*"))
    with pytest.raises(NotFoundError):
        service.get(dataset.id)


def test_preview_head_and_tail(db_session: Session, settings: Settings) -> None:
    dataset = _import(db_session, settings)
    service = DatasetService(db_session, get_data_paths(settings))

    head = service.preview(dataset.id, part="head", rows=1)
    tail = service.preview(dataset.id, part="tail", rows=1)

    assert len(head.rows) == 1
    assert len(tail.rows) == 1
    assert head.rows[0].open == 100.0
    assert tail.rows[0].open == 100.5


def test_list_bars_returns_paginated_rows(db_session: Session, settings: Settings) -> None:
    dataset = _import(db_session, settings)
    service = DatasetService(db_session, get_data_paths(settings))

    page = service.list_bars(dataset.id, offset=1, limit=1)

    assert page.total == 2
    assert page.offset == 1
    assert page.limit == 1
    assert len(page.rows) == 1
    assert page.rows[0].open == 100.5


def test_preview_raises_not_found_when_import_failed(
    db_session: Session, settings: Settings
) -> None:
    service = ImportService(db_session, get_data_paths(settings))
    dataset = service.import_csv(
        name="Bad",
        symbol="X",
        exchange="NSE",
        timeframe=Timeframe.M1,
        content=b"timestamp,open\n2024-01-01,1\n",
    )

    dataset_service = DatasetService(db_session, get_data_paths(settings))
    with pytest.raises(NotFoundError):
        dataset_service.preview(dataset.id, part="head", rows=20)
