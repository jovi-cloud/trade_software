"""Dataset import pipeline: upload -> validate -> immutable version -> metadata.

Uses the production data pipeline in ``app.data.data_pipeline``. The execution
engine never consumes raw CSV, Excel, or unvalidated files. Each import creates
a new immutable ``DatasetVersion``; parquet files are never overwritten.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.hashing import hash_file
from app.core.paths import DataPaths
from app.data.data_pipeline import PipelineConfig, SessionConfig, run_pipeline_from_bytes
from app.data.data_pipeline.importer import infer_columns
from app.data.data_pipeline.parquet_writer import write_bars
from app.data.data_pipeline.serialize import pipeline_report_to_dict
from app.data.errors import MissingColumnsError
from app.data.fingerprint import compute_dataset_fingerprint, resolve_timeframe_label
from app.domain.dataset_status import (
    dataset_status_from_version,
    dataset_status_to_import_status,
    version_status_from_pipeline,
)
from app.domain.enums import DatasetStatus, DatasetVersionStatus, ImportStatus, Timeframe
from app.models.data_import import DataImport
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.repositories.data_import_repo import DataImportRepository
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.dataset_version_repo import DatasetVersionRepository


class ImportService:
    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.repo = DatasetRepository(session)
        self.version_repo = DatasetVersionRepository(session)
        self.import_repo = DataImportRepository(session)

    def preview(
        self,
        *,
        filename: str,
        content: bytes,
    ) -> dict[str, object]:
        if not content:
            raise ValidationError("Uploaded file is empty")
        return infer_columns(Path(filename), content=content)

    def import_file(
        self,
        *,
        name: str,
        symbol: str,
        exchange: str,
        timeframe: Timeframe | None,
        content: bytes,
        filename: str,
        timezone: str = "UTC",
        session_open: str = "09:15",
        session_close: str = "15:30",
        column_mapping: dict[str, str] | None = None,
        dataset_id: str | None = None,
    ) -> Dataset:
        name = name.strip()
        symbol = symbol.strip().upper()
        exchange = exchange.strip()
        if not name or not symbol or not exchange:
            raise ValidationError("name, symbol and exchange must not be blank")
        if not content:
            raise ValidationError("Uploaded file is empty")

        original_filename = Path(filename).name
        suffix = Path(original_filename).suffix.lower() or ".csv"

        if dataset_id is not None:
            dataset = self.repo.get(dataset_id)
            if dataset is None:
                raise NotFoundError(f"Dataset '{dataset_id}' not found")
        else:
            dataset = Dataset(
                name=name,
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe.value if timeframe else "",
                file_path="",
                original_filename=original_filename,
                timezone=timezone,
                row_count=0,
                status=DatasetStatus.UPLOADED,
                import_status=ImportStatus.PROCESSING,
            )
            self.repo.add(dataset)
            self.session.commit()
            self.session.refresh(dataset)

        version_number = self.version_repo.next_version_number(dataset.id)
        import_suffix = f"{dataset.id}_v{version_number}{suffix}"
        original_path = self.paths.imports / import_suffix
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_bytes(content)
        file_hash = hash_file(original_path)

        data_import = DataImport(
            dataset_id=dataset.id,
            filename=original_filename,
            file_hash=file_hash,
            rows_read=0,
            rows_written=0,
            rows_rejected=0,
            duplicates_removed=0,
            gaps_detected=0,
            status=ImportStatus.PROCESSING,
        )
        self.import_repo.add(data_import)
        self.session.flush()

        version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=version_number,
            data_import_id=data_import.id,
            file_path="",
            file_size_bytes=0,
            parquet_hash="",
            fingerprint="",
            timezone=timezone,
            status=DatasetVersionStatus.VALIDATING,
        )
        self.version_repo.add(version)
        data_import.dataset_version_id = version.id
        dataset.status = DatasetStatus.VALIDATING
        dataset.import_status = ImportStatus.PROCESSING
        self.session.commit()

        self._process(
            dataset,
            version,
            data_import,
            content=content,
            filename=original_filename,
            column_mapping=column_mapping,
            timezone=timezone,
            session_open=session_open,
            session_close=session_close,
            timeframe=timeframe,
        )
        return dataset

    def import_csv(
        self,
        *,
        name: str,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        content: bytes,
    ) -> Dataset:
        """Backward-compatible CSV import entry point."""
        return self.import_file(
            name=name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            content=content,
            filename="upload.csv",
        )

    def import_new_version(
        self,
        dataset_id: str,
        *,
        content: bytes,
        filename: str,
        timezone: str | None = None,
        session_open: str = "09:15",
        session_close: str = "15:30",
        column_mapping: dict[str, str] | None = None,
        timeframe: Timeframe | None = None,
    ) -> Dataset:
        dataset = self.repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")
        return self.import_file(
            name=dataset.name,
            symbol=dataset.symbol,
            exchange=dataset.exchange,
            timeframe=timeframe or (Timeframe(dataset.timeframe) if dataset.timeframe else None),
            content=content,
            filename=filename,
            timezone=timezone or dataset.timezone,
            session_open=session_open,
            session_close=session_close,
            column_mapping=column_mapping,
            dataset_id=dataset.id,
        )

    def revalidate(self, dataset_id: str) -> Dataset:
        dataset = self.repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")

        latest_import = self.import_repo.latest_for_dataset(dataset_id)
        if latest_import is None:
            raise NotFoundError("This dataset has no import history to revalidate")

        suffix = Path(latest_import.filename).suffix.lower() or ".csv"
        candidates = sorted(self.paths.imports.glob(f"{dataset.id}_v*{suffix}"), reverse=True)
        if not candidates:
            legacy = self.paths.imports / f"{dataset.id}{suffix}"
            if legacy.exists():
                candidates = [legacy]
            else:
                legacy_csv = self.paths.imports / f"{dataset.id}.csv"
                if legacy_csv.exists():
                    candidates = [legacy_csv]
                else:
                    raise NotFoundError("The original file for this dataset is no longer on disk")

        content = candidates[0].read_bytes()
        return self.import_new_version(
            dataset_id,
            content=content,
            filename=latest_import.filename,
            timezone=dataset.timezone,
            timeframe=Timeframe(dataset.timeframe) if dataset.timeframe else None,
        )

    def _process(
        self,
        dataset: Dataset,
        version: DatasetVersion,
        data_import: DataImport,
        *,
        content: bytes,
        filename: str,
        timezone: str = "UTC",
        session_open: str = "09:15",
        session_close: str = "15:30",
        column_mapping: dict[str, str] | None = None,
        timeframe: Timeframe | None = None,
    ) -> None:
        config = PipelineConfig(
            timeframe=timeframe or (Timeframe(dataset.timeframe) if dataset.timeframe else None),
            column_mapping=column_mapping or {},
            session=SessionConfig(
                open_time=session_open,
                close_time=session_close,
                timezone=timezone,
            ),
            instrument=dataset.symbol,
            exchange=dataset.exchange,
        )

        try:
            result = run_pipeline_from_bytes(content, filename=filename, config=config)
        except MissingColumnsError as exc:
            self._mark_failed(dataset, version, data_import, error=str(exc))
            return

        report = result.report
        report_dict = pipeline_report_to_dict(report)

        duplicates_removed = sum(
            a.count for a in report.cleaning.actions if a.action == "remove_duplicate_rows"
        )
        data_import.rows_read = report.validation.total_rows
        data_import.rows_written = report.validation.valid_rows
        data_import.rows_rejected = report.validation.total_rows - report.validation.valid_rows
        data_import.duplicates_removed = duplicates_removed
        data_import.gaps_detected = report.gaps.missing_bars
        data_import.quality_score = report.quality_score
        data_import.report_json = json.dumps(report_dict)

        version_status = version_status_from_pipeline(
            rejected=report.rejected,
            valid_rows=report.validation.valid_rows,
        )
        version.report_json = json.dumps(report_dict)
        version.quality_score = report.quality_score
        detected = report.timeframe.detected
        version.detected_timeframe = detected.value if detected else None
        version.timezone = timezone
        version.status = version_status.value

        if version_status == DatasetVersionStatus.VALID:
            parquet_path = self.paths.dataset_version_parquet(dataset.id, version.version_number)
            write_bars(result.bars, parquet_path)
            timeframe_label = resolve_timeframe_label(
                dataset.timeframe or (timeframe.value if timeframe else None),
                version.detected_timeframe,
            )
            version.file_path = str(parquet_path.relative_to(self.paths.root))
            version.file_size_bytes = parquet_path.stat().st_size
            version.parquet_hash = hash_file(parquet_path)
            version.fingerprint = compute_dataset_fingerprint(
                result.bars,
                timeframe=timeframe_label,
                timezone=timezone,
            )
            version.row_count = report.validation.valid_rows
            version.start_date = report.validation.start_date
            version.end_date = report.validation.end_date
            data_import.status = ImportStatus.COMPLETED
            data_import.error_message = None
        else:
            data_import.status = ImportStatus.FAILED
            data_import.error_message = report.rejection_reason or "No valid rows after validation"
            version.error_message = data_import.error_message

        dataset_status = dataset_status_from_version(version_status)
        self._apply_current_version(dataset, version, data_import, dataset_status, report_dict)
        self.session.commit()
        self.session.refresh(dataset)

    def _mark_failed(
        self,
        dataset: Dataset,
        version: DatasetVersion,
        data_import: DataImport,
        *,
        error: str,
    ) -> None:
        dataset.status = DatasetStatus.FAILED
        dataset.import_status = ImportStatus.FAILED
        dataset.validation_errors = json.dumps({"error": error})
        version.status = DatasetVersionStatus.FAILED.value
        version.error_message = error
        data_import.status = ImportStatus.FAILED
        data_import.error_message = error
        self.session.commit()
        self.session.refresh(dataset)

    def _apply_current_version(
        self,
        dataset: Dataset,
        version: DatasetVersion,
        data_import: DataImport,
        dataset_status: DatasetStatus,
        report_dict: dict[str, object],
    ) -> None:
        dataset.current_version_id = version.id
        dataset.current_version_number = version.version_number
        dataset.status = dataset_status
        dataset.import_status = dataset_status_to_import_status(dataset_status).value
        dataset.file_hash = data_import.file_hash
        dataset.quality_score = version.quality_score
        dataset.detected_timeframe = version.detected_timeframe
        dataset.timezone = version.timezone
        dataset.validation_errors = json.dumps(report_dict)
        if version.status == DatasetVersionStatus.VALID.value:
            dataset.file_path = version.file_path
            dataset.row_count = version.row_count
            dataset.start_date = version.start_date
            dataset.end_date = version.end_date
            if not dataset.timeframe and version.detected_timeframe:
                dataset.timeframe = version.detected_timeframe
        if dataset.original_filename is None:
            dataset.original_filename = data_import.filename
