"""Dataset use cases: CRUD, search/sort, soft delete (+ file cleanup), preview."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.paths import DataPaths
from app.data import store
from app.db.base import utcnow
from app.domain.dataset_status import import_status_to_dataset_status
from app.domain.enums import (
    DatasetLifecycle,
    DatasetStatus,
    DatasetVersionStatus,
    ImportStatus,
    Timeframe,
)
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.repositories.backtest_run_repo import BacktestRunRepository
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.dataset_version_repo import DatasetVersionRepository
from app.schemas.dataset import (
    BarRow,
    DatasetBacktestReference,
    DatasetPreview,
    DatasetRead,
    DatasetReferencesRead,
    DatasetValidationReport,
    DatasetVersionRead,
    PipelineReportRead,
)

ALLOWED_SORT_COLUMNS = {"updated_at", "name", "row_count"}
MAX_PAGE_SIZE = 100
MAX_PREVIEW_ROWS = 500


def _parse_pipeline_report(
    raw: str | None,
) -> tuple[PipelineReportRead | None, DatasetValidationReport | None, str | None]:
    if not raw:
        return None, None, None
    parsed = json.loads(raw)
    if "error" in parsed:
        return None, None, str(parsed["error"])
    if "validation" in parsed:
        pipeline_report = PipelineReportRead.model_validate(parsed)
        return pipeline_report, pipeline_report.validation, None
    report = DatasetValidationReport.model_validate(parsed)
    return None, report, None


def dataset_to_read(dataset: Dataset, *, version_count: int = 0) -> DatasetRead:
    """ORM -> API DTO, unpacking the JSON-encoded pipeline report."""
    pipeline_report, report, import_error = _parse_pipeline_report(dataset.validation_errors)

    detected_tf = None
    if dataset.detected_timeframe:
        detected_tf = Timeframe(dataset.detected_timeframe)

    tf_value = dataset.timeframe or dataset.detected_timeframe or Timeframe.M1.value
    status = (
        DatasetStatus(dataset.status)
        if dataset.status
        else import_status_to_dataset_status(dataset.import_status)
    )
    lifecycle = (
        DatasetLifecycle(dataset.lifecycle)
        if getattr(dataset, "lifecycle", None)
        else DatasetLifecycle.ACTIVE
    )
    return DatasetRead(
        id=dataset.id,
        name=dataset.name,
        symbol=dataset.symbol,
        exchange=dataset.exchange,
        timeframe=Timeframe(tf_value),
        file_path=dataset.file_path,
        original_filename=dataset.original_filename,
        file_hash=dataset.file_hash,
        timezone=dataset.timezone or "UTC",
        detected_timeframe=detected_tf,
        quality_score=dataset.quality_score,
        row_count=dataset.row_count,
        start_date=dataset.start_date,
        end_date=dataset.end_date,
        status=status,
        lifecycle=lifecycle,
        import_status=ImportStatus(dataset.import_status),
        current_version_id=dataset.current_version_id,
        current_version_number=dataset.current_version_number,
        version_count=version_count,
        validation_report=report,
        pipeline_report=pipeline_report,
        import_error=import_error,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


def version_to_read(version: DatasetVersion) -> DatasetVersionRead:
    pipeline_report, report, _ = _parse_pipeline_report(version.report_json)
    detected_tf = None
    if version.detected_timeframe:
        detected_tf = Timeframe(version.detected_timeframe)
    return DatasetVersionRead(
        id=version.id,
        dataset_id=version.dataset_id,
        version_number=version.version_number,
        data_import_id=version.data_import_id,
        file_path=version.file_path,
        file_size_bytes=version.file_size_bytes,
        parquet_hash=version.parquet_hash,
        fingerprint=version.fingerprint,
        row_count=version.row_count,
        start_date=version.start_date,
        end_date=version.end_date,
        timezone=version.timezone,
        detected_timeframe=detected_tf,
        quality_score=version.quality_score,
        status=version.status,
        error_message=version.error_message,
        validation_report=report,
        pipeline_report=pipeline_report,
        created_at=version.created_at,
    )


class DatasetService:
    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.repo = DatasetRepository(session)
        self.version_repo = DatasetVersionRepository(session)
        self.run_repo = BacktestRunRepository(session)

    def get(self, dataset_id: str) -> Dataset:
        dataset = self.repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")
        return dataset

    def get_read(self, dataset_id: str) -> DatasetRead:
        dataset = self.get(dataset_id)
        return dataset_to_read(
            dataset, version_count=self.version_repo.count_for_dataset(dataset_id)
        )

    def list_datasets(
        self,
        *,
        q: str | None,
        timeframe: Timeframe | None,
        sort: str,
        order: str,
        limit: int,
        offset: int,
    ) -> tuple[list[DatasetRead], int]:
        sort_column = sort if sort in ALLOWED_SORT_COLUMNS else "updated_at"
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        offset = max(0, offset)
        items, total = self.repo.search(
            q=q.strip() if q else None,
            timeframe=timeframe,
            sort_column=sort_column,
            descending=order != "asc",
            limit=limit,
            offset=offset,
        )
        return [dataset_to_read(item) for item in items], total

    def list_versions(self, dataset_id: str) -> list[DatasetVersionRead]:
        self.get(dataset_id)
        return [
            version_to_read(version) for version in self.version_repo.list_for_dataset(dataset_id)
        ]

    def get_version(self, dataset_id: str, version_number: int) -> DatasetVersionRead:
        version = self.version_repo.get_by_dataset_and_number(dataset_id, version_number)
        if version is None:
            raise NotFoundError(f"Dataset '{dataset_id}' has no version {version_number}")
        return version_to_read(version)

    def resolve_version_parquet(
        self, dataset_id: str, version_number: int | None = None
    ) -> tuple[DatasetVersion, Path]:
        dataset = self.get(dataset_id)
        if version_number is None:
            if dataset.current_version_id is None:
                raise NotFoundError("This dataset has no completed version yet")
            version = self.version_repo.get(dataset.current_version_id)
        else:
            version = self.version_repo.get_by_dataset_and_number(dataset_id, version_number)
        if version is None:
            raise NotFoundError(f"Dataset version not found for '{dataset.name}'")
        if version.status != DatasetVersionStatus.VALID.value:
            raise NotFoundError(f"Dataset version v{version.version_number} is not valid")
        path = self.paths.root / version.file_path
        if not path.exists():
            raise NotFoundError(f"The stored bars for dataset '{dataset.name}' are missing")
        return version, path

    def references(self, dataset_id: str, *, limit: int = 20) -> DatasetReferencesRead:
        self.get(dataset_id)
        count = self.run_repo.count_by_dataset_id(dataset_id)
        rows = self.run_repo.list_by_dataset_id(dataset_id, limit=limit)
        return DatasetReferencesRead(
            reference_count=count,
            backtest_runs=[
                DatasetBacktestReference(
                    run_id=run.id,
                    strategy_name=strategy_name,
                    dataset_version_number=run.dataset_version_number,
                    execution_completed_at=run.execution_completed_at,
                )
                for run, strategy_name, _dataset_name in rows
            ],
        )

    def archive(self, dataset_id: str) -> Dataset:
        dataset = self.get(dataset_id)
        if dataset.lifecycle == DatasetLifecycle.ARCHIVED:
            return dataset
        dataset.lifecycle = DatasetLifecycle.ARCHIVED
        self.session.commit()
        self.session.refresh(dataset)
        return dataset

    def delete(self, dataset_id: str) -> None:
        dataset = self.get(dataset_id)
        reference_count = self.run_repo.count_by_dataset_id(dataset_id)
        if reference_count > 0:
            refs = self.references(dataset_id, limit=10)
            raise ConflictError(
                f"This dataset is referenced by {reference_count} historical backtest(s) "
                "and cannot be deleted.",
                details={
                    "reference_count": reference_count,
                    "backtest_runs": [item.model_dump(mode="json") for item in refs.backtest_runs],
                },
            )

        dataset.lifecycle = DatasetLifecycle.DELETED
        dataset.deleted_at = utcnow()
        self.session.commit()

        self._remove_files(dataset)

    def _remove_files(self, dataset: Dataset) -> None:
        for path in self.paths.imports.glob(f"{dataset.id}*"):
            store.delete(path)
        version_dir = self.paths.market / dataset.id
        if version_dir.exists():
            shutil.rmtree(version_dir, ignore_errors=True)
        legacy_parquet = self.paths.market / f"{dataset.id}.parquet"
        store.delete(legacy_parquet)
        if dataset.file_path:
            store.delete(self.paths.root / dataset.file_path)

    def preview(
        self,
        dataset_id: str,
        *,
        part: str,
        rows: int,
        version_number: int | None = None,
    ) -> DatasetPreview:
        version, parquet_path = self.resolve_version_parquet(dataset_id, version_number)
        _ = version
        rows = max(1, min(rows, MAX_PREVIEW_ROWS))
        frame = (
            store.read_head(parquet_path, rows)
            if part == "head"
            else store.read_tail(parquet_path, rows)
        )
        return DatasetPreview(rows=[BarRow(**row) for row in frame.to_dicts()])
