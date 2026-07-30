"""Dataset Library: CRUD, import, preview, re-validation, immutable versions.

Validate -> call service -> return.
"""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import DbSession, Paths
from app.domain.enums import Timeframe
from app.repositories.data_import_repo import DataImportRepository
from app.schemas.common import Page
from app.schemas.dataset import (
    DataImportRead,
    DatasetPreview,
    DatasetRead,
    DatasetReferencesRead,
    DatasetVersionRead,
    ImportPreviewResponse,
    PipelineReportRead,
)
from app.services.dataset_service import DatasetService
from app.services.import_service import ImportService

router = APIRouter(prefix="/datasets", tags=["datasets"])

SortField = Literal["updated_at", "name", "row_count"]
SortOrder = Literal["asc", "desc"]
PreviewPart = Literal["head", "tail"]


def _import_to_read(record: object) -> DataImportRead:
    from app.models.data_import import DataImport

    assert isinstance(record, DataImport)
    report = None
    if record.report_json:
        report = PipelineReportRead.model_validate(json.loads(record.report_json))
    return DataImportRead(
        id=record.id,
        dataset_id=record.dataset_id,
        dataset_version_id=record.dataset_version_id,
        filename=record.filename,
        file_hash=record.file_hash,
        rows_read=record.rows_read,
        rows_written=record.rows_written,
        rows_rejected=record.rows_rejected,
        duplicates_removed=record.duplicates_removed,
        gaps_detected=record.gaps_detected,
        quality_score=record.quality_score,
        status=record.status,
        error_message=record.error_message,
        report=report,
        created_at=record.created_at,
    )


@router.get("", response_model=Page[DatasetRead], summary="List datasets")
def list_datasets(
    db: DbSession,
    paths: Paths,
    q: str | None = None,
    timeframe: Timeframe | None = None,
    sort: SortField = "updated_at",
    order: SortOrder = "desc",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[DatasetRead]:
    service = DatasetService(db, paths)
    items, total = service.list_datasets(
        q=q, timeframe=timeframe, sort=sort, order=order, limit=limit, offset=offset
    )
    return Page[DatasetRead](items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/import/preview",
    response_model=ImportPreviewResponse,
    summary="Preview column mapping for an uploaded file",
)
async def preview_import(
    file: UploadFile,
) -> ImportPreviewResponse:
    from pathlib import Path

    from app.data.data_pipeline.importer import infer_columns

    content = await file.read()
    result = infer_columns(Path(file.filename or "upload.csv"), content=content)
    return ImportPreviewResponse.model_validate(result)


@router.post(
    "/import",
    response_model=DatasetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a market data file and import it as a dataset",
)
async def import_dataset(
    db: DbSession,
    paths: Paths,
    file: UploadFile,
    name: str = Form(...),
    symbol: str = Form(...),
    exchange: str = Form(...),
    timeframe: Timeframe | None = Form(default=None),
    timezone: str = Form(default="UTC"),
    session_open: str = Form(default="09:15"),
    session_close: str = Form(default="15:30"),
    column_mapping: str | None = Form(default=None),
) -> DatasetRead:
    content = await file.read()
    mapping: dict[str, str] | None = None
    if column_mapping:
        mapping = json.loads(column_mapping)
    service = ImportService(db, paths)
    dataset = service.import_file(
        name=name,
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        content=content,
        filename=file.filename or "upload.csv",
        timezone=timezone,
        session_open=session_open,
        session_close=session_close,
        column_mapping=mapping,
    )
    return DatasetService(db, paths).get_read(dataset.id)


@router.get("/{dataset_id}", response_model=DatasetRead, summary="Get a dataset")
def get_dataset(dataset_id: str, db: DbSession, paths: Paths) -> DatasetRead:
    return DatasetService(db, paths).get_read(dataset_id)


@router.get(
    "/{dataset_id}/versions",
    response_model=list[DatasetVersionRead],
    summary="List immutable versions for a dataset",
)
def list_dataset_versions(dataset_id: str, db: DbSession, paths: Paths) -> list[DatasetVersionRead]:
    return DatasetService(db, paths).list_versions(dataset_id)


@router.get(
    "/{dataset_id}/versions/{version_number}",
    response_model=DatasetVersionRead,
    summary="Get one dataset version",
)
def get_dataset_version(
    dataset_id: str, version_number: int, db: DbSession, paths: Paths
) -> DatasetVersionRead:
    return DatasetService(db, paths).get_version(dataset_id, version_number)


@router.get(
    "/{dataset_id}/versions/{version_number}/download",
    summary="Download the parquet file for a dataset version",
)
def download_dataset_version(
    dataset_id: str, version_number: int, db: DbSession, paths: Paths
) -> FileResponse:
    service = DatasetService(db, paths)
    version, parquet_path = service.resolve_version_parquet(dataset_id, version_number)
    return FileResponse(
        path=parquet_path,
        filename=f"{dataset_id}_v{version.version_number}.parquet",
        media_type="application/octet-stream",
    )


@router.post(
    "/{dataset_id}/import",
    response_model=DatasetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Import a new immutable version for an existing dataset",
)
async def import_dataset_version(
    dataset_id: str,
    db: DbSession,
    paths: Paths,
    file: UploadFile,
    timezone: str | None = Form(default=None),
    session_open: str = Form(default="09:15"),
    session_close: str = Form(default="15:30"),
    column_mapping: str | None = Form(default=None),
    timeframe: Timeframe | None = Form(default=None),
) -> DatasetRead:
    content = await file.read()
    mapping: dict[str, str] | None = None
    if column_mapping:
        mapping = json.loads(column_mapping)
    service = ImportService(db, paths)
    dataset = service.import_new_version(
        dataset_id,
        content=content,
        filename=file.filename or "upload.csv",
        timezone=timezone,
        session_open=session_open,
        session_close=session_close,
        column_mapping=mapping,
        timeframe=timeframe,
    )
    return DatasetService(db, paths).get_read(dataset.id)


@router.get(
    "/{dataset_id}/imports",
    response_model=list[DataImportRead],
    summary="List import history for a dataset",
)
def list_dataset_imports(dataset_id: str, db: DbSession, paths: Paths) -> list[DataImportRead]:
    service = DatasetService(db, paths)
    service.get(dataset_id)
    records = DataImportRepository(db).list_for_dataset(dataset_id)
    return [_import_to_read(record) for record in records]


@router.get(
    "/{dataset_id}/imports/{import_id}",
    response_model=DataImportRead,
    summary="Get one import record with its validation report",
)
def get_dataset_import(
    dataset_id: str, import_id: str, db: DbSession, paths: Paths
) -> DataImportRead:
    service = DatasetService(db, paths)
    service.get(dataset_id)
    record = DataImportRepository(db).get(import_id)
    if record is None or record.dataset_id != dataset_id:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(f"Import '{import_id}' not found for dataset '{dataset_id}'")
    return _import_to_read(record)


@router.get(
    "/{dataset_id}/references",
    response_model=DatasetReferencesRead,
    summary="List backtest runs that depend on this dataset",
)
def dataset_references(dataset_id: str, db: DbSession, paths: Paths) -> DatasetReferencesRead:
    return DatasetService(db, paths).references(dataset_id)


@router.post(
    "/{dataset_id}/archive",
    response_model=DatasetRead,
    summary="Archive a dataset so it cannot be used for new backtests",
)
def archive_dataset(dataset_id: str, db: DbSession, paths: Paths) -> DatasetRead:
    service = DatasetService(db, paths)
    dataset = service.archive(dataset_id)
    return service.get_read(dataset.id)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a dataset")
def delete_dataset(dataset_id: str, db: DbSession, paths: Paths) -> Response:
    service = DatasetService(db, paths)
    service.delete(dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{dataset_id}/validate",
    response_model=DatasetRead,
    summary="Re-run validation from the latest stored upload (creates a new version)",
)
def revalidate_dataset(dataset_id: str, db: DbSession, paths: Paths) -> DatasetRead:
    service = ImportService(db, paths)
    dataset = service.revalidate(dataset_id)
    return DatasetService(db, paths).get_read(dataset.id)


@router.get(
    "/{dataset_id}/preview",
    response_model=DatasetPreview,
    summary="Preview first/last rows without loading the full file",
)
def preview_dataset(
    dataset_id: str,
    db: DbSession,
    paths: Paths,
    part: PreviewPart = "head",
    rows: int = Query(default=20, ge=1, le=500),
    version: int | None = Query(default=None, ge=1),
) -> DatasetPreview:
    service = DatasetService(db, paths)
    return service.preview(dataset_id, part=part, rows=rows, version_number=version)
