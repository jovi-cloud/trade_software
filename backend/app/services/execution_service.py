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
from app.domain.explain import ExplainLevel
from app.engine.bars import BarIterator
from app.engine.explain.timeline import assemble_timeline, service_collector
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
        explain_level: ExplainLevel = ExplainLevel.TRADES_ONLY,
        instrument: str | None = None,
        timeframe: str | None = None,
    ) -> ExecutionConfig:
        return ExecutionConfig(
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
            explain_level=explain_level,
            instrument=instrument,
            timeframe=timeframe,
        )

    def execute(
        self, *, strategy_id: str, dataset_id: str, config: ExecutionConfig
    ) -> ExecutionResult:
        source = self._load_source(strategy_id)
        dataset = self.dataset_repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")
        try:
            rows = load_bars(self._resolve_parquet(dataset_id))
        except InvalidBarsError as exc:
            raise ValidationError(str(exc)) from exc

        clock_ms = int(rows[0]["ts"]) if rows else 0
        service_events = service_collector(config.explain_level, timestamp_ms=clock_ms)
        if config.explain_level is not ExplainLevel.NONE:
            service_events.set_context(instrument=dataset.name, timeframe=dataset.timeframe)
        dataset_event = None
        if config.explain_level is not ExplainLevel.NONE:
            service_events.record_dataset_loaded(
                bar_count=len(rows),
                dataset_name=dataset.name,
            )
            dataset_event = service_events.events[-1]

        engine = ExecutionEngine(config)
        result = engine.run(strategy_source=source, bars=BarIterator.from_rows(rows))
        enriched = self.metrics_service.enrich(result, initial_capital=config.initial_capital)
        candles, entry_markers, exit_markers = self.chart_builder.build(rows, enriched.trades)

        metrics_event = None
        charts_event = None
        if config.explain_level is not ExplainLevel.NONE:
            service_events.set_clock(
                int(rows[-1]["ts"]) if rows else clock_ms,
            )
            service_events.record_metrics_generated(trade_count=enriched.trade_count)
            metrics_event = service_events.events[-1]
            service_events.record_charts_generated(
                candle_count=len(candles),
                marker_count=len(entry_markers) + len(exit_markers),
            )
            charts_event = service_events.events[-1]

        explain_events = assemble_timeline(
            enriched.explain_events,
            level=config.explain_level,
            dataset_event=dataset_event,
            metrics_event=metrics_event,
            charts_event=charts_event,
        )

        return replace(
            enriched,
            candles=candles,
            entry_markers=entry_markers,
            exit_markers=exit_markers,
            explain_events=explain_events,
            explain_level=config.explain_level,
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
