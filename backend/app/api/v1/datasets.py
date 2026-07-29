"""Dataset Library: CRUD, CSV import, preview, re-validation.

Validate -> call service -> return.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Form, Query, Response, UploadFile, status

from app.api.deps import DbSession, Paths
from app.domain.enums import Timeframe
from app.schemas.common import Page
from app.schemas.dataset import DatasetPreview, DatasetRead
from app.services.dataset_service import DatasetService, dataset_to_read
from app.services.import_service import ImportService

router = APIRouter(prefix="/datasets", tags=["datasets"])

SortField = Literal["updated_at", "name", "row_count"]
SortOrder = Literal["asc", "desc"]
PreviewPart = Literal["head", "tail"]


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
    items, total = service.list(
        q=q, timeframe=timeframe, sort=sort, order=order, limit=limit, offset=offset
    )
    return Page[DatasetRead](
        items=[dataset_to_read(item) for item in items], total=total, limit=limit, offset=offset
    )


@router.post(
    "/import",
    response_model=DatasetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a CSV and import it as a dataset",
)
async def import_dataset(
    db: DbSession,
    paths: Paths,
    file: UploadFile,
    name: str = Form(...),
    symbol: str = Form(...),
    exchange: str = Form(...),
    timeframe: Timeframe = Form(...),
) -> DatasetRead:
    content = await file.read()
    service = ImportService(db, paths)
    dataset = service.import_csv(
        name=name, symbol=symbol, exchange=exchange, timeframe=timeframe, content=content
    )
    return dataset_to_read(dataset)


@router.get("/{dataset_id}", response_model=DatasetRead, summary="Get a dataset")
def get_dataset(dataset_id: str, db: DbSession, paths: Paths) -> DatasetRead:
    service = DatasetService(db, paths)
    return dataset_to_read(service.get(dataset_id))


@router.delete(
    "/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a dataset"
)
def delete_dataset(dataset_id: str, db: DbSession, paths: Paths) -> Response:
    service = DatasetService(db, paths)
    service.delete(dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{dataset_id}/validate",
    response_model=DatasetRead,
    summary="Re-run validation and re-import from the originally uploaded CSV",
)
def revalidate_dataset(dataset_id: str, db: DbSession, paths: Paths) -> DatasetRead:
    service = ImportService(db, paths)
    return dataset_to_read(service.revalidate(dataset_id))


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
) -> DatasetPreview:
    service = DatasetService(db, paths)
    return service.preview(dataset_id, part=part, rows=rows)
