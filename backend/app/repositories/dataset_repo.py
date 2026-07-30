"""Dataset persistence. SQL queries only - no business rules (ARCHITECTURE.md 2.1)."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.domain.enums import DatasetLifecycle
from app.models.dataset import Dataset


class DatasetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _readable(self) -> Select[tuple[Dataset]]:
        return select(Dataset).where(
            Dataset.deleted_at.is_(None),
            Dataset.lifecycle != DatasetLifecycle.DELETED,
        )

    def _selectable(self) -> Select[tuple[Dataset]]:
        return select(Dataset).where(
            Dataset.deleted_at.is_(None),
            Dataset.lifecycle == DatasetLifecycle.ACTIVE,
        )

    def get(self, dataset_id: str) -> Dataset | None:
        return self.session.scalars(self._readable().where(Dataset.id == dataset_id)).first()

    def get_selectable(self, dataset_id: str) -> Dataset | None:
        return self.session.scalars(self._selectable().where(Dataset.id == dataset_id)).first()

    def search(
        self,
        *,
        q: str | None,
        timeframe: str | None,
        sort_column: str,
        descending: bool,
        limit: int,
        offset: int,
        lifecycle: str | None = None,
    ) -> tuple[list[Dataset], int]:
        stmt = self._readable()
        if lifecycle:
            stmt = stmt.where(Dataset.lifecycle == lifecycle)
        if q:
            like = f"%{q}%"
            stmt = stmt.where((Dataset.name.ilike(like)) | (Dataset.symbol.ilike(like)))
        if timeframe:
            stmt = stmt.where(Dataset.timeframe == timeframe)

        columns = {
            "updated_at": Dataset.updated_at,
            "name": Dataset.name,
            "row_count": Dataset.row_count,
        }
        column = columns.get(sort_column, Dataset.updated_at)
        stmt = stmt.order_by(column.desc() if descending else column.asc())

        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(self.session.scalars(stmt.limit(limit).offset(offset)))
        return items, total

    def add(self, dataset: Dataset) -> Dataset:
        self.session.add(dataset)
        self.session.flush()
        return dataset
