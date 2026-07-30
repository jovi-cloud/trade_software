"""ImportService against a real temp SQLite file + real temp data dir (ARCHITECTURE.md 9)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.paths import get_data_paths
from app.data import store
from app.domain.enums import ImportStatus, Timeframe
from app.repositories.dataset_version_repo import DatasetVersionRepository
from app.services.import_service import ImportService

VALID_CSV = (
    b"timestamp,open,high,low,close,volume\n"
    b"2024-01-01 09:15:00,100,101,99,100.5,1000\n"
    b"2024-01-01 09:16:00,100.5,102,100,101.5,1200\n"
    b"2024-01-01 09:17:00,101.5,103,101,102.5,900\n"
)


def _service(session: Session, settings: Settings) -> ImportService:
    return ImportService(session, get_data_paths(settings))


def test_import_csv_creates_completed_dataset(db_session: Session, settings: Settings) -> None:
    service = _service(db_session, settings)

    dataset = service.import_csv(
        name="NIFTY 1m",
        symbol="nifty",
        exchange="NSE",
        timeframe=Timeframe.M1,
        content=VALID_CSV,
    )

    assert dataset.import_status == ImportStatus.COMPLETED
    assert dataset.symbol == "NIFTY"
    assert dataset.row_count == 3
    assert dataset.current_version_number == 1
    assert dataset.start_date is not None
    assert dataset.end_date is not None
    assert dataset.file_path
    assert (get_data_paths(settings).root / dataset.file_path).exists()


def test_import_csv_writes_parquet_readable_by_store(
    db_session: Session, settings: Settings
) -> None:
    service = _service(db_session, settings)
    paths = get_data_paths(settings)

    dataset = service.import_csv(
        name="NIFTY 1m", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=VALID_CSV
    )

    frame = store.read_head(paths.root / dataset.file_path, 10)
    assert frame.height == 3
    assert frame.columns == ["ts", "open", "high", "low", "close", "volume"]


def test_import_csv_stores_original_file_for_revalidation(
    db_session: Session, settings: Settings
) -> None:
    service = _service(db_session, settings)
    paths = get_data_paths(settings)

    dataset = service.import_csv(
        name="NIFTY 1m", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=VALID_CSV
    )

    stored = list(paths.imports.glob(f"{dataset.id}_v1.*"))
    assert stored
    assert stored[0].read_bytes() == VALID_CSV
    assert dataset.quality_score is not None
    assert dataset.quality_score >= 70


def test_import_csv_with_missing_columns_marks_failed(
    db_session: Session, settings: Settings
) -> None:
    service = _service(db_session, settings)
    bad_csv = b"timestamp,open,high,low,close\n2024-01-01 09:15:00,1,2,3,4\n"

    dataset = service.import_csv(
        name="Bad Import", symbol="X", exchange="NSE", timeframe=Timeframe.M1, content=bad_csv
    )

    assert dataset.import_status == ImportStatus.FAILED
    assert dataset.validation_errors is not None
    assert "volume" in dataset.validation_errors


def test_import_csv_rejects_blank_name(db_session: Session, settings: Settings) -> None:
    service = _service(db_session, settings)

    with pytest.raises(ValidationError):
        service.import_csv(
            name="   ", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=VALID_CSV
        )


def test_import_csv_rejects_empty_file(db_session: Session, settings: Settings) -> None:
    service = _service(db_session, settings)

    with pytest.raises(ValidationError):
        service.import_csv(
            name="Empty", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=b""
        )


def test_revalidate_reprocesses_stored_csv(db_session: Session, settings: Settings) -> None:
    service = _service(db_session, settings)
    dataset = service.import_csv(
        name="NIFTY 1m", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=VALID_CSV
    )

    revalidated = service.revalidate(dataset.id)

    assert revalidated.id == dataset.id
    assert revalidated.import_status == ImportStatus.COMPLETED
    assert revalidated.row_count == 3
    assert revalidated.current_version_number == 2
    versions = DatasetVersionRepository(db_session).list_for_dataset(dataset.id)
    assert len(versions) == 2


def test_revalidate_missing_dataset_raises_not_found(
    db_session: Session, settings: Settings
) -> None:
    service = _service(db_session, settings)

    with pytest.raises(NotFoundError):
        service.revalidate("does-not-exist")
