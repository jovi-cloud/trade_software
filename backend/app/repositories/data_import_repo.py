"""Data import audit trail persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_import import DataImport


class DataImportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, record: DataImport) -> None:
        self.session.add(record)

    def list_for_dataset(self, dataset_id: str) -> list[DataImport]:
        stmt = (
            select(DataImport)
            .where(DataImport.dataset_id == dataset_id)
            .order_by(DataImport.created_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def latest_for_dataset(self, dataset_id: str) -> DataImport | None:
        stmt = (
            select(DataImport)
            .where(DataImport.dataset_id == dataset_id)
            .order_by(DataImport.created_at.desc())
            .limit(1)
        )
        return self.session.scalars(stmt).first()

    def get(self, import_id: str) -> DataImport | None:
        return self.session.get(DataImport, import_id)
