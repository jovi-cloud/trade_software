"""Map dataset lifecycle states to legacy import status values."""

from __future__ import annotations

from app.domain.enums import DatasetStatus, DatasetVersionStatus, ImportStatus


def dataset_status_to_import_status(status: DatasetStatus) -> ImportStatus:
    if status == DatasetStatus.VALIDATING:
        return ImportStatus.PROCESSING
    if status == DatasetStatus.VALID:
        return ImportStatus.COMPLETED
    return ImportStatus.FAILED


def import_status_to_dataset_status(status: ImportStatus | str) -> DatasetStatus:
    value = ImportStatus(status)
    if value == ImportStatus.PROCESSING:
        return DatasetStatus.VALIDATING
    if value == ImportStatus.COMPLETED:
        return DatasetStatus.VALID
    return DatasetStatus.FAILED


def version_status_from_pipeline(*, rejected: bool, valid_rows: int) -> DatasetVersionStatus:
    if rejected:
        return DatasetVersionStatus.INVALID
    if valid_rows > 0:
        return DatasetVersionStatus.VALID
    return DatasetVersionStatus.FAILED


def dataset_status_from_version(status: DatasetVersionStatus) -> DatasetStatus:
    if status == DatasetVersionStatus.VALIDATING:
        return DatasetStatus.VALIDATING
    if status == DatasetVersionStatus.VALID:
        return DatasetStatus.VALID
    if status == DatasetVersionStatus.INVALID:
        return DatasetStatus.INVALID
    return DatasetStatus.FAILED
