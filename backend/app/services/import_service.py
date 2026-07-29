"""Dataset import pipeline: upload -> validate -> parquet -> metadata (ARCHITECTURE.md 2.3).

Runs synchronously within the request. A CSV import is seconds of work at
desktop-file sizes; the job queue (ARCHITECTURE.md 2.4) arrives in Phase 3 for
the genuinely long-running backtest workload, and is deliberately not pulled
forward here - "simple until proven otherwise" (ARCHITECTURE.md 0.5).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.paths import DataPaths
from app.data import store
from app.data.errors import MissingColumnsError
from app.data.readers.csv_reader import read_csv
from app.data.validator import ValidationReport, validate_and_clean
from app.domain.enums import ImportStatus, Timeframe
from app.models.dataset import Dataset
from app.repositories.dataset_repo import DatasetRepository


def _report_to_json(report: ValidationReport) -> str:
    data = asdict(report)
    for key in ("start_date", "end_date"):
        if data[key] is not None:
            data[key] = data[key].isoformat()
    return json.dumps(data)


class ImportService:
    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.repo = DatasetRepository(session)

    def import_csv(
        self,
        *,
        name: str,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        content: bytes,
    ) -> Dataset:
        name = name.strip()
        symbol = symbol.strip().upper()
        exchange = exchange.strip()
        if not name or not symbol or not exchange:
            raise ValidationError("name, symbol and exchange must not be blank")
        if not content:
            raise ValidationError("Uploaded file is empty")

        dataset = Dataset(
            name=name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            file_path="",
            row_count=0,
            import_status=ImportStatus.PROCESSING,
        )
        self.repo.add(dataset)
        self.session.commit()
        self.session.refresh(dataset)

        original_path = self.paths.imports / f"{dataset.id}.csv"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_bytes(content)

        self._process(dataset, original_path)
        return dataset

    def revalidate(self, dataset_id: str) -> Dataset:
        dataset = self.repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")

        original_path = self.paths.imports / f"{dataset.id}.csv"
        if not original_path.exists():
            raise NotFoundError("The original CSV for this dataset is no longer on disk")

        self._process(dataset, original_path)
        return dataset

    def _process(self, dataset: Dataset, csv_path: Path) -> None:
        try:
            raw = read_csv(csv_path)
        except MissingColumnsError as exc:
            dataset.import_status = ImportStatus.FAILED
            dataset.validation_errors = json.dumps({"error": str(exc)})
            self.session.commit()
            self.session.refresh(dataset)
            return

        bars, report = validate_and_clean(raw, Timeframe(dataset.timeframe))

        parquet_path = self.paths.market / f"{dataset.id}.parquet"
        store.write_parquet(bars, parquet_path)

        dataset.file_path = str(parquet_path.relative_to(self.paths.root))
        dataset.row_count = report.valid_rows
        dataset.start_date = report.start_date
        dataset.end_date = report.end_date
        dataset.import_status = (
            ImportStatus.COMPLETED if report.valid_rows > 0 else ImportStatus.FAILED
        )
        dataset.validation_errors = _report_to_json(report)
        self.session.commit()
        self.session.refresh(dataset)
