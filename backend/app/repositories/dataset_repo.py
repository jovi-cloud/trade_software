"""Dataset persistence. SQL queries only - no business rules (ARCHITECTURE.md 2.1)."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset


class DatasetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _active(self) -> Select[tuple[Dataset]]:
        return select(Dataset).where(Dataset.deleted_at.is_(None))

    def get(self, dataset_id: str) -> Dataset | None:
        return self.session.scalars(self._active().where(Dataset.id == dataset_id)).first()

    def search(
        self,
        *,
        q: str | None,
        timeframe: str | None,
        sort_column: str,
        descending: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Dataset], int]:
        stmt = self._active()
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
