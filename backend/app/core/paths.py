"""Resolution and creation of the on-disk layout under ``data/``.

Every path the application writes to is derived here, so that backing the
project up is always "zip the data directory".
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


class DataPaths:
    """Typed view over the data directory layout (ARCHITECTURE.md 1)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def database(self) -> Path:
        return self.root / "app.db"

    @property
    def market(self) -> Path:
        """Bar storage: market/{symbol}/{timeframe}/{year}.parquet"""
        return self.root / "market"

    @property
    def artifacts(self) -> Path:
        """Per-run outputs: artifacts/{run_id}/equity.parquet"""
        return self.root / "artifacts"

    @property
    def imports(self) -> Path:
        """Staged uploads awaiting processing."""
        return self.root / "imports"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    def dataset_version_parquet(self, dataset_id: str, version_number: int) -> Path:
        """Immutable parquet for one dataset version: market/{id}/v{n}.parquet."""
        return self.market / dataset_id / f"v{version_number}.parquet"

    def run_artifacts(self, run_id: str) -> Path:
        """Directory holding one run's artifacts: artifacts/{run_id}/."""
        return self.artifacts / run_id

    def run_decisions_parquet(self, run_id: str) -> Path:
        """Per-bar decision log for one run: artifacts/{run_id}/decisions.parquet."""
        return self.run_artifacts(run_id) / "decisions.parquet"

    def ensure(self) -> None:
        """Create every directory. Idempotent; called once at startup."""
        for path in (self.root, self.market, self.artifacts, self.imports, self.logs):
            path.mkdir(parents=True, exist_ok=True)


def get_data_paths(settings: Settings) -> DataPaths:
    return DataPaths(settings.data_dir)
