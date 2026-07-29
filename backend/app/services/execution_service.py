"""Run a saved strategy against a saved dataset.

The seam between persistence and the engine (ARCHITECTURE.md 6): load the
config and the bars, call the engine, hand back its result. The engine never
learns that a database exists.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.paths import DataPaths
from app.data.errors import InvalidBarsError
from app.data.loader import load_bars
from app.domain.enums import ImportStatus
from app.engine.bars import BarIterator
from app.engine.results.chart_data import ChartDataBuilder
from app.engine.results.result import ExecutionResult
from app.engine.runner import ExecutionConfig, ExecutionEngine
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.strategy_code_repo import StrategyCodeRepository
from app.repositories.strategy_repo import StrategyRepository
from app.services.metrics_service import MetricsService


class ExecutionService:
    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.strategy_repo = StrategyRepository(session)
        self.code_repo = StrategyCodeRepository(session)
        self.dataset_repo = DatasetRepository(session)
        self.metrics_service = MetricsService()
        self.chart_builder = ChartDataBuilder()

    @staticmethod
    def build_config(
        *,
        initial_capital: float,
        commission: float,
        slippage: float,
    ) -> ExecutionConfig:
        return ExecutionConfig(
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
        )

    def execute(
        self, *, strategy_id: str, dataset_id: str, config: ExecutionConfig
    ) -> ExecutionResult:
        source = self._load_source(strategy_id)
        try:
            rows = load_bars(self._resolve_parquet(dataset_id))
        except InvalidBarsError as exc:
            raise ValidationError(str(exc)) from exc
        engine = ExecutionEngine(config)
        result = engine.run(strategy_source=source, bars=BarIterator.from_rows(rows))
        enriched = self.metrics_service.enrich(result, initial_capital=config.initial_capital)
        candles, entry_markers, exit_markers = self.chart_builder.build(rows, enriched.trades)
        return replace(
            enriched,
            candles=candles,
            entry_markers=entry_markers,
            exit_markers=exit_markers,
        )

    def _load_source(self, strategy_id: str) -> str:
        if self.strategy_repo.get(strategy_id) is None:
            raise NotFoundError(f"Strategy '{strategy_id}' not found")

        code = self.code_repo.get_by_strategy_id(strategy_id)
        if code is None or not code.code.strip():
            raise ValidationError("This strategy has no code saved yet")
        return code.code

    def _resolve_parquet(self, dataset_id: str) -> Path:
        dataset = self.dataset_repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")
        if dataset.import_status != ImportStatus.COMPLETED:
            raise ValidationError(
                f"Dataset '{dataset.name}' is not ready to run against "
                f"(import status: {dataset.import_status})"
            )

        path = self.paths.root / dataset.file_path
        if not path.exists():
            raise NotFoundError(f"The stored bars for dataset '{dataset.name}' are missing")
        return path
