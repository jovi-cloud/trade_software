"""Run a saved strategy against a saved dataset.

The seam between persistence and the engine (ARCHITECTURE.md 6): load the
config and the bars, call the engine, hand back its result. The engine never
learns that a database exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.paths import DataPaths
from app.data.errors import InvalidBarsError
from app.data.loader import load_bars
from app.domain.enums import (
    DatasetVersionStatus,
    MarketType,
    StrategyStatus,
    Timeframe,
)
from app.domain.explain import ExplainLevel
from app.engine.bars import BarIterator
from app.engine.explain.timeline import assemble_timeline, service_collector
from app.engine.results.chart_data import ChartDataBuilder
from app.engine.results.result import ExecutionResult
from app.engine.runner import ExecutionConfig, ExecutionEngine
from app.engine.strategy.definition import StrategyDefinition
from app.engine.strategy.params import ParamValue
from app.engine.strategy.provider import (
    LibraryStrategyProvider,
    SourceStrategyProvider,
    StrategyProvider,
)
from app.models.dataset_version import DatasetVersion
from app.models.strategy import Strategy
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.dataset_version_repo import DatasetVersionRepository
from app.repositories.strategy_code_repo import StrategyCodeRepository
from app.repositories.strategy_repo import StrategyRepository
from app.services.metrics_service import MetricsService
from app.services.strategy_library_service import StrategyLibraryService

#: How many "<name> (Library N)" variants to try before giving up on a container
#: name. A collision needs a user strategy already holding the plain name; more
#: than a handful means something is wrong, not that the loop is too short.
MAX_CONTAINER_NAME_ATTEMPTS = 20
#: A library strategy is not tied to one instrument - the dataset decides.
LIBRARY_CONTAINER_INSTRUMENT = "Any"


@dataclass(frozen=True)
class ResolvedStrategy:
    """What will be run, and the text that records it on the run.

    ``snapshot`` is the reproducibility record: source code for a hand-written
    strategy, a pinned id/version/parameter descriptor for a library one. The
    library fields are what let a saved result offer "run this again" without
    re-deriving anything from that text.
    """

    provider: StrategyProvider
    snapshot: str
    library_strategy_id: str | None = None
    library_strategy_version: str | None = None
    params: dict[str, ParamValue] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedDatasetVersion:
    """Immutable dataset version selected for one execution."""

    id: str
    version_number: int
    parquet_path: Path
    fingerprint: str
    quality_score: int | None
    data_import_id: str | None
    imported_at: datetime | None


@dataclass(frozen=True)
class RunPlan:
    """Everything one execution needs, resolved and validated up front.

    Built in a single call so the router stays validate -> call service ->
    return, and so the whole "which strategy, which container, how much
    explainability" decision is testable without going through HTTP.
    """

    strategy_id: str
    dataset_id: str
    config: ExecutionConfig
    strategy: ResolvedStrategy
    dataset_version: ResolvedDatasetVersion


class ExecutionService:
    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.strategy_repo = StrategyRepository(session)
        self.code_repo = StrategyCodeRepository(session)
        self.dataset_repo = DatasetRepository(session)
        self.version_repo = DatasetVersionRepository(session)
        self.metrics_service = MetricsService()
        self.chart_builder = ChartDataBuilder()
        self.library = StrategyLibraryService()

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

    def plan(
        self,
        *,
        dataset_id: str,
        strategy_id: str | None = None,
        library_strategy_id: str | None = None,
        strategy_params: Mapping[str, object] | None = None,
        initial_capital: float,
        commission: float,
        slippage: float,
        explain_level: ExplainLevel | None = None,
        dataset_version_id: str | None = None,
        dataset_version_number: int | None = None,
    ) -> RunPlan:
        """Resolve one run request into something the engine can be handed.

        Order matters. Everything that can reject the request - the dataset,
        the strategy, its parameters - is checked before the container is
        resolved, because resolving one may *create* it. A rejected run must
        not leave an empty research record behind.
        """
        dataset = self.dataset_repo.get_selectable(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found or is not available")

        dataset_version = self.resolve_dataset_version(
            dataset_id,
            dataset_version_id=dataset_version_id,
            dataset_version_number=dataset_version_number,
        )

        resolved = self.resolve_strategy(
            strategy_id=strategy_id,
            library_strategy_id=library_strategy_id,
            strategy_params=strategy_params,
        )
        container_id = self.resolve_container(
            strategy_id=strategy_id, library_strategy_id=library_strategy_id
        )
        config = self.build_config(
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
            explain_level=(
                explain_level
                if explain_level is not None
                else self.default_explain_level(library_strategy_id)
            ),
            instrument=dataset.name,
            timeframe=dataset.timeframe,
        )
        return RunPlan(
            strategy_id=container_id,
            dataset_id=dataset_id,
            config=config,
            strategy=resolved,
            dataset_version=dataset_version,
        )

    def default_explain_level(self, library_strategy_id: str | None) -> ExplainLevel:
        """Explainability to collect when the caller expressed no preference.

        A library strategy traces every condition it evaluates; defaulting such
        a run to trades-only would silently discard the Decision Inspector's
        entire input. Hand-written code keeps the long-standing default.
        """
        if library_strategy_id is None:
            return ExplainLevel.TRADES_ONLY
        return self.library.get(library_strategy_id).recommended_explain_level

    def resolve_container(self, *, strategy_id: str | None, library_strategy_id: str | None) -> str:
        """The ``strategies`` row this run will be recorded against.

        Every run needs one - it is the research container the run history,
        journal and notes hang off. A library run launched straight from the
        library has no such row yet, so the first one creates it. That keeps
        "browse -> configure -> run" a single uninterrupted flow instead of
        detouring through a create-strategy form.
        """
        if strategy_id is not None:
            if self.strategy_repo.get(strategy_id) is None:
                raise NotFoundError(f"Strategy '{strategy_id}' not found")
            return strategy_id
        if library_strategy_id is None:
            raise ValidationError("Choose a strategy to run")
        return self._ensure_library_container(self.library.get(library_strategy_id)).id

    def resolve_strategy(
        self,
        *,
        strategy_id: str | None = None,
        library_strategy_id: str | None = None,
        strategy_params: Mapping[str, object] | None = None,
    ) -> ResolvedStrategy:
        """Decide what to run: the strategy's saved code, or a library strategy.

        A library run still belongs to a saved strategy record - that is the
        research container the run history, journal and notes hang off. What
        changes is only *which code executes*, which is why the saved strategy
        does not need code of its own in that case.
        """
        if library_strategy_id is None:
            if strategy_id is None:
                raise ValidationError("Choose a strategy to run")
            source = self._load_source(strategy_id)
            return ResolvedStrategy(provider=SourceStrategyProvider(source), snapshot=source)

        if strategy_id is not None and self.strategy_repo.get(strategy_id) is None:
            raise NotFoundError(f"Strategy '{strategy_id}' not found")

        definition = self.library.get(library_strategy_id)
        if not definition.is_valid:
            reasons = "; ".join(finding.message for finding in definition.validation.errors)
            raise ValidationError(
                f"Library strategy '{library_strategy_id}' failed validation: {reasons}"
            )

        report = definition.validate_params(strategy_params)
        if not report.is_valid:
            raise ValidationError(
                "; ".join(finding.message for finding in report.errors),
                details={
                    "strategy_id": library_strategy_id,
                    "errors": [
                        {"param": finding.param, "code": finding.code, "message": finding.message}
                        for finding in report.errors
                    ],
                },
            )

        return ResolvedStrategy(
            provider=LibraryStrategyProvider(
                definition.strategy_class,
                report.values,
                strategy_id=definition.id,
                version=definition.metadata.version,
            ),
            snapshot=definition.snapshot(report.values),
            library_strategy_id=definition.id,
            library_strategy_version=definition.metadata.version,
            params=dict(report.values),
        )

    def execute(
        self,
        *,
        strategy_id: str,
        dataset_id: str,
        config: ExecutionConfig,
        strategy: ResolvedStrategy | None = None,
        dataset_version: ResolvedDatasetVersion | None = None,
    ) -> ExecutionResult:
        resolved = strategy or self.resolve_strategy(strategy_id=strategy_id)
        dataset = self.dataset_repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")
        version = dataset_version or self.resolve_dataset_version(dataset_id)
        try:
            rows = load_bars(version.parquet_path)
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
        result = engine.run(bars=BarIterator.from_rows(rows), strategy=resolved.provider)
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

    def _ensure_library_container(self, definition: StrategyDefinition) -> Strategy:
        """Find, or create once, the research container for a library strategy."""
        existing = self.strategy_repo.get_by_library_strategy_id(definition.id)
        if existing is not None:
            return existing

        metadata = definition.metadata
        container = Strategy(
            name=self._available_container_name(metadata.name),
            description=metadata.description or metadata.name,
            hypothesis=metadata.documentation.overview or None,
            market_type=metadata.markets[0] if metadata.markets else MarketType.EQUITY,
            instrument=LIBRARY_CONTAINER_INSTRUMENT,
            timeframe=metadata.timeframes[0] if metadata.timeframes else Timeframe.M1,
            status=StrategyStatus.TESTING,
            tags=", ".join(metadata.tags) or None,
            library_strategy_id=definition.id,
        )
        self.strategy_repo.add(container)
        self.session.commit()
        self.session.refresh(container)
        return container

    def _available_container_name(self, preferred: str) -> str:
        """``preferred``, or the first free variant of it.

        ``strategies.name`` is unique, and a user is perfectly entitled to have
        already named an idea "Opening Range Breakout".
        """
        if self.strategy_repo.get_by_name(preferred) is None:
            return preferred
        for attempt in range(2, MAX_CONTAINER_NAME_ATTEMPTS + 2):
            candidate = f"{preferred} (Library {attempt})"
            if self.strategy_repo.get_by_name(candidate) is None:
                return candidate
        raise ValidationError(
            f"Could not find an unused strategy name for '{preferred}'; "
            "rename or delete the existing ones"
        )

    def resolve_dataset_version(
        self,
        dataset_id: str,
        *,
        dataset_version_id: str | None = None,
        dataset_version_number: int | None = None,
    ) -> ResolvedDatasetVersion:
        """Resolve the immutable parquet version for one execution."""
        dataset = self.dataset_repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")

        version: DatasetVersion | None
        if dataset_version_id is not None:
            version = self.version_repo.get(dataset_version_id)
            if version is None or version.dataset_id != dataset_id:
                raise NotFoundError(f"Dataset version '{dataset_version_id}' not found")
        elif dataset_version_number is not None:
            version = self.version_repo.get_by_dataset_and_number(
                dataset_id, dataset_version_number
            )
            if version is None:
                raise NotFoundError(
                    f"Dataset '{dataset.name}' has no version {dataset_version_number}"
                )
        else:
            if dataset.current_version_id is None:
                raise ValidationError(
                    f"Dataset '{dataset.name}' is not ready to run against (no valid version)"
                )
            version = self.version_repo.get(dataset.current_version_id)

        if version is None or version.status != DatasetVersionStatus.VALID.value:
            raise ValidationError(
                f"Dataset '{dataset.name}' is not ready to run against "
                f"(version status: {version.status if version else 'missing'})"
            )

        path = self.paths.root / version.file_path
        if not path.exists():
            raise NotFoundError(f"The stored bars for dataset '{dataset.name}' are missing")

        imported_at: datetime | None = None
        if version.data_import_id:
            from app.repositories.data_import_repo import DataImportRepository

            data_import = DataImportRepository(self.session).get(version.data_import_id)
            if data_import is not None:
                imported_at = data_import.created_at

        return ResolvedDatasetVersion(
            id=version.id,
            version_number=version.version_number,
            parquet_path=path,
            fingerprint=version.fingerprint,
            quality_score=version.quality_score,
            data_import_id=version.data_import_id,
            imported_at=imported_at or version.created_at,
        )

    def _load_source(self, strategy_id: str) -> str:
        if self.strategy_repo.get(strategy_id) is None:
            raise NotFoundError(f"Strategy '{strategy_id}' not found")

        code = self.code_repo.get_by_strategy_id(strategy_id)
        if code is None or not code.code.strip():
            raise ValidationError("This strategy has no code saved yet")
        return code.code

