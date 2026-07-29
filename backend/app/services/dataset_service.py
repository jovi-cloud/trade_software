"""Dataset use cases: CRUD, search/sort, soft delete (+ file cleanup), preview."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.paths import DataPaths
from app.data import store
from app.db.base import utcnow
from app.domain.enums import ImportStatus, Timeframe
from app.models.dataset import Dataset
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.dataset import BarRow, DatasetPreview, DatasetRead, DatasetValidationReport

ALLOWED_SORT_COLUMNS = {"updated_at", "name", "row_count"}
MAX_PAGE_SIZE = 100
MAX_PREVIEW_ROWS = 500


def dataset_to_read(dataset: Dataset) -> DatasetRead:
    """ORM -> API DTO, unpacking the JSON-encoded validation report.

    ``validation_errors`` holds either a full report or, when the import failed
    before validation could run, ``{"error": "..."}``.
    """
    report = None
    import_error = None
    if dataset.validation_errors:
        parsed = json.loads(dataset.validation_errors)
        if "error" in parsed:
            import_error = str(parsed["error"])
        else:
            report = DatasetValidationReport.model_validate(parsed)

    return DatasetRead(
        id=dataset.id,
        name=dataset.name,
        symbol=dataset.symbol,
        exchange=dataset.exchange,
        timeframe=Timeframe(dataset.timeframe),
        file_path=dataset.file_path,
        row_count=dataset.row_count,
        start_date=dataset.start_date,
        end_date=dataset.end_date,
        import_status=ImportStatus(dataset.import_status),
        validation_report=report,
        import_error=import_error,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


class DatasetService:
    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.repo = DatasetRepository(session)

    def get(self, dataset_id: str) -> Dataset:
        dataset = self.repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")
        return dataset

    def list(
        self,
        *,
        q: str | None,
        timeframe: Timeframe | None,
        sort: str,
        order: str,
        limit: int,
        offset: int,
    ) -> tuple[list[Dataset], int]:
        sort_column = sort if sort in ALLOWED_SORT_COLUMNS else "updated_at"
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        offset = max(0, offset)
        return self.repo.search(
            q=q.strip() if q else None,
            timeframe=timeframe,
            sort_column=sort_column,
            descending=order != "asc",
            limit=limit,
            offset=offset,
        )

    def delete(self, dataset_id: str) -> None:
        dataset = self.get(dataset_id)
        dataset.deleted_at = utcnow()
        self.session.commit()

        store.delete(self.paths.imports / f"{dataset.id}.csv")
        if dataset.file_path:
            store.delete(self.paths.root / dataset.file_path)

    def preview(self, dataset_id: str, *, part: str, rows: int) -> DatasetPreview:
        dataset = self.get(dataset_id)
        if dataset.import_status != ImportStatus.COMPLETED or not dataset.file_path:
            raise NotFoundError("This dataset has no data to preview yet")

        rows = max(1, min(rows, MAX_PREVIEW_ROWS))
        parquet_path = self.paths.root / dataset.file_path
        frame = (
            store.read_head(parquet_path, rows)
            if part == "head"
            else store.read_tail(parquet_path, rows)
        )
        return DatasetPreview(rows=[BarRow(**row) for row in frame.to_dicts()])
