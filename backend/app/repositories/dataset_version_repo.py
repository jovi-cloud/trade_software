"""Dataset version persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dataset_version import DatasetVersion


class DatasetVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, version: DatasetVersion) -> DatasetVersion:
        self.session.add(version)
        self.session.flush()
        return version

    def get(self, version_id: str) -> DatasetVersion | None:
        return self.session.get(DatasetVersion, version_id)

    def get_by_dataset_and_number(
        self, dataset_id: str, version_number: int
    ) -> DatasetVersion | None:
        stmt = select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.version_number == version_number,
        )
        return self.session.scalars(stmt).first()

    def list_for_dataset(self, dataset_id: str) -> list[DatasetVersion]:
        stmt = (
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
        )
        return list(self.session.scalars(stmt).all())

    def next_version_number(self, dataset_id: str) -> int:
        stmt = select(func.max(DatasetVersion.version_number)).where(
            DatasetVersion.dataset_id == dataset_id
        )
        current = self.session.scalar(stmt)
        return 1 if current is None else int(current) + 1

    def count_for_dataset(self, dataset_id: str) -> int:
        stmt = select(func.count()).where(DatasetVersion.dataset_id == dataset_id)
        return int(self.session.scalar(stmt) or 0)
