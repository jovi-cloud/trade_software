"""Run a saved strategy against a saved dataset.

The seam between persistence and the engine (ARCHITECTURE.md 6): load the
config and the bars, call the engine, hand back its result. The engine never
learns that a database exists.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import JobCancelledError, NotFoundError, ValidationError
from app.core.ids import new_id
from app.core.paths import DataPaths
from app.data.decision_store import ParquetDecisionSink
from app.data.data_pipeline.price_anomaly_days import (
    PriceAnomalyTradeSkipOptions,
    resolve_no_trade_days,
)
from app.data.errors import InvalidBarsError
from app.data.loader import bar_timestamp_at, iter_bar_rows, load_bar_frame
from app.domain.enums import (
    DatasetVersionStatus,
    MarketType,
    StrategyStatus,
    Timeframe,
)
from app.domain.explain import ExplainLevel
from app.engine.bars import BarIterator, bar_from_row
from app.engine.explain import MAX_PER_BAR_EXPLAIN_EVENTS
from app.engine.explain.timeline import assemble_timeline, service_collector
from app.engine.results.chart_data import CandleCollector, ChartDataBuilder, TrailingStopCollector
from app.engine.results.result import ExecutionResult
from app.engine.runner import ExecutionConfig, ExecutionEngine
from app.engine.strategy.definition import StrategyDefinition
from app.engine.strategy.params import ParamValue
from app.engine.strategy.provider import (
    LibraryStrategyProvider,
    SourceStrategyProvider,
    StrategyProvider,
)
from app.engine.strategy.risk import StopLossOverride
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
#: Retained for the mark-to-market events that still live in the JSON timeline.
#: It no longer bounds the *decision* log: that goes to a columnar artifact at
#: ~31 bytes per bar, so a 194,553-bar run logs every bar in about 6 MB and there
#: is nothing left for a bar limit to protect against.
FULL_EXPLAIN_EVENT_BUDGET = MAX_PER_BAR_EXPLAIN_EVENTS


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
    #: Bars in this version, known before the parquet is opened. Lets the run
    #: workflow size its explainability budget against the actual dataset.
    row_count: int = 0


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
    #: Allocated here rather than at insert time so the decision log can be
    #: streamed straight to its final artifact path during the run. The same id
    #: is handed to ``BacktestRunService.create_from_execution``.
    run_id: str = field(default_factory=new_id)


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
        session_timezone: str = "UTC",
        no_trade_session_dates: frozenset[str] | None = None,
        max_trades_per_day: int | None = None,
        entry_window_start: str | None = None,
        entry_window_end: str | None = None,
        stop_loss_override: StopLossOverride | None = None,
        session_exit_at: str | None = None,
    ) -> ExecutionConfig:
        return ExecutionConfig(
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
            explain_level=explain_level,
            instrument=instrument,
            timeframe=timeframe,
            session_timezone=session_timezone,
            no_trade_session_dates=no_trade_session_dates or frozenset(),
            max_trades_per_day=max_trades_per_day,
            entry_window_start=entry_window_start,
            entry_window_end=entry_window_end,
            stop_loss_override=stop_loss_override,
            session_exit_at=session_exit_at,
        )

    @staticmethod
    def resolve_session_exit_at(
        *,
        enable_session_exit: bool,
        session_exit_at: str,
    ) -> str | None:
        if not enable_session_exit:
            return None
        from app.engine.execution.entry_window import normalize_hhmm

        return normalize_hhmm(session_exit_at)

    @staticmethod
    def resolve_stop_loss_override(
        *,
        override_stop_loss: bool,
        stop_loss_override_mode: str | None,
        stop_loss_value: float | None,
    ) -> StopLossOverride | None:
        if not override_stop_loss or stop_loss_override_mode is None:
            return None
        if stop_loss_override_mode == "disabled":
            return StopLossOverride(mode="disabled")
        if stop_loss_override_mode == "percent":
            return StopLossOverride(mode="percent", percent=stop_loss_value)
        return StopLossOverride(mode="atr", atr_multiple=stop_loss_value)

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
        skip_trades_on_price_anomaly_days: bool = False,
        skip_trades_on_intraday_anomalies_10pct: bool = True,
        skip_trades_on_intraday_anomalies_20pct: bool = True,
        skip_trades_on_cross_day_anomalies_10pct: bool = True,
        skip_trades_on_cross_day_anomalies_20pct: bool = True,
        max_trades_per_day: int | None = None,
        entry_window_start: str | None = None,
        entry_window_end: str | None = None,
        override_stop_loss: bool = False,
        stop_loss_override_mode: str | None = None,
        stop_loss_value: float | None = None,
        enable_session_exit: bool = True,
        session_exit_at: str = "14:55",
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
        no_trade_days = frozenset[str]()
        if skip_trades_on_price_anomaly_days:
            version_row = self.version_repo.get(dataset_version.id)
            no_trade_days = resolve_no_trade_days(
                version_row.report_json if version_row is not None else None,
                options=PriceAnomalyTradeSkipOptions(
                    intraday_over_10pct=skip_trades_on_intraday_anomalies_10pct,
                    intraday_over_20pct=skip_trades_on_intraday_anomalies_20pct,
                    cross_day_over_10pct=skip_trades_on_cross_day_anomalies_10pct,
                    cross_day_over_20pct=skip_trades_on_cross_day_anomalies_20pct,
                ),
            )
        config = self.build_config(
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
            explain_level=(
                explain_level
                if explain_level is not None
                else self.default_explain_level(
                    library_strategy_id, bar_count=dataset_version.row_count
                )
            ),
            instrument=dataset.name,
            timeframe=dataset.timeframe,
            session_timezone=dataset.timezone,
            no_trade_session_dates=no_trade_days,
            max_trades_per_day=max_trades_per_day,
            entry_window_start=entry_window_start,
            entry_window_end=entry_window_end,
            stop_loss_override=self.resolve_stop_loss_override(
                override_stop_loss=override_stop_loss,
                stop_loss_override_mode=stop_loss_override_mode,
                stop_loss_value=stop_loss_value,
            ),
            session_exit_at=self.resolve_session_exit_at(
                enable_session_exit=enable_session_exit,
                session_exit_at=session_exit_at,
            ),
        )
        return RunPlan(
            strategy_id=container_id,
            dataset_id=dataset_id,
            config=config,
            strategy=resolved,
            dataset_version=dataset_version,
        )

    def default_explain_level(
        self, library_strategy_id: str | None, *, bar_count: int = 0
    ) -> ExplainLevel:
        """Explainability to collect when the caller expressed no preference.

        A library strategy traces every condition it evaluates; defaulting such
        a run to trades-only would silently discard the Decision Inspector's
        entire input. Hand-written code keeps the long-standing default.

        ``bar_count`` used to downgrade long runs to trades-only, because FULL
        wrote per-bar JSON events that the engine's budget then truncated - so a
        big dataset would have produced a decision log that arrived incomplete.
        The decision log is now columnar and uncapped (~31 bytes per bar), so
        length is no longer a reason to record less, and the parameter is kept
        only so callers do not have to change.
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
        on_progress: Callable[..., None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        max_bars: int | None = None,
        run_id: str | None = None,
    ) -> ExecutionResult:
        """Replay one strategy against one dataset version.

        ``run_id`` is the id the run will be saved under. Supplying it turns on
        the per-bar decision log, streamed to that run's artifact directory as
        the bar loop goes; the caller must persist the run under the same id.
        """
        resolved = strategy or self.resolve_strategy(strategy_id=strategy_id)
        dataset = self.dataset_repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")
        version = dataset_version or self.resolve_dataset_version(dataset_id)
        try:
            # Columnar and validated, but not yet a single Python row object:
            # the bars are streamed out of this frame one at a time below.
            frame = load_bar_frame(version.parquet_path)
        except InvalidBarsError as exc:
            raise ValidationError(str(exc)) from exc

        if should_cancel is not None and should_cancel():
            raise JobCancelledError("Backtest cancelled")

        total_bars = frame.height if max_bars is None else min(max_bars, frame.height)
        if on_progress is not None:
            on_progress(bars_processed=0, total_bars=total_bars, phase="loading")

        # Read off the ts column rather than from a materialised first/last row.
        clock_ms = bar_timestamp_at(frame, 0) if total_bars else 0
        final_ts = bar_timestamp_at(frame, total_bars - 1) if total_bars else clock_ms
        service_events = service_collector(config.explain_level, timestamp_ms=clock_ms)
        if config.explain_level is not ExplainLevel.NONE:
            service_events.set_context(instrument=dataset.name, timeframe=dataset.timeframe)
        dataset_event = None
        if config.explain_level is not ExplainLevel.NONE:
            service_events.record_dataset_loaded(
                bar_count=total_bars,
                dataset_name=dataset.name,
            )
            dataset_event = service_events.events[-1]

        engine = ExecutionEngine(config)

        def engine_progress(done: int, total: int) -> None:
            if on_progress is not None:
                on_progress(bars_processed=done, total_bars=total, phase="engine")

        # The chart's candles are collected off the replay stream, so the bars
        # are converted once and no full copy of them outlives the run.
        candle_collector = CandleCollector()
        bar_stream = candle_collector.tap(
            bar_from_row(row) for row in iter_bar_rows(frame, limit=total_bars)
        )

        # The decision log is what FULL now means: every indicator value,
        # condition verdict and calculation operand, for every bar. It is written
        # straight to the run's artifact path so nothing is held in memory and
        # nothing needs truncating.
        decision_sink = (
            ParquetDecisionSink(self.paths.run_decisions_parquet(run_id))
            if run_id is not None and config.explain_level is ExplainLevel.FULL
            else None
        )

        result = engine.run(
            bars=BarIterator.streaming(bar_stream, count=total_bars),
            strategy=resolved.provider,
            on_progress=engine_progress,
            should_cancel=should_cancel,
            decision_sink=decision_sink,
        )
        if config.no_trade_session_dates:
            result = replace(
                result,
                warnings=(
                    *result.warnings,
                    (
                        "New entries were disabled on "
                        f"{len(config.no_trade_session_dates)} session day(s) flagged for "
                        "price anomalies. Bars were still replayed; exits were allowed."
                    ),
                ),
            )
        if config.max_trades_per_day is not None:
            result = replace(
                result,
                warnings=(
                    *result.warnings,
                    (
                        f"New entries were capped at {config.max_trades_per_day} per "
                        "exchange-local session day. Exits were still allowed."
                    ),
                ),
            )
        if config.entry_window_start is not None and config.entry_window_end is not None:
            result = replace(
                result,
                warnings=(
                    *result.warnings,
                    (
                        "New entries were limited to exchange-local "
                        f"{config.entry_window_start}–{config.entry_window_end}. "
                        "Exits were still allowed."
                    ),
                ),
            )
        if config.stop_loss_override is not None:
            override = config.stop_loss_override
            if override.mode == "disabled":
                message = "The strategy stop loss was disabled for this run."
            elif override.mode == "percent":
                message = (
                    f"The strategy stop loss was overridden to {override.percent:g}% "
                    "of entry price for this run."
                )
            else:
                message = (
                    f"The strategy stop loss was overridden to {override.atr_multiple:g}x "
                    "ATR at entry for this run."
                )
            result = replace(result, warnings=(*result.warnings, message))
        if config.session_exit_at is not None:
            result = replace(
                result,
                warnings=(
                    *result.warnings,
                    (
                        f"Open positions were flattened at {config.session_exit_at} "
                        f"{config.session_timezone} when stop-loss and take-profit did not fire."
                    ),
                ),
            )
        if should_cancel is not None and should_cancel():
            raise JobCancelledError("Backtest cancelled")
        enriched = self.metrics_service.enrich(result, initial_capital=config.initial_capital)
        candles = candle_collector.candles
        entry_markers, exit_markers = self.chart_builder.markers(enriched.trades)

        metrics_event = None
        charts_event = None
        if config.explain_level is not ExplainLevel.NONE:
            service_events.set_clock(final_ts)
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
        preferred = metadata.name
        last_error: IntegrityError | None = None

        for _ in range(MAX_CONTAINER_NAME_ATTEMPTS):
            name = self._available_container_name(preferred)
            container = Strategy(
                name=name,
                description=metadata.description or metadata.name,
                hypothesis=metadata.documentation.overview or None,
                market_type=metadata.markets[0] if metadata.markets else MarketType.EQUITY,
                instrument=LIBRARY_CONTAINER_INSTRUMENT,
                timeframe=metadata.timeframes[0] if metadata.timeframes else Timeframe.M1,
                status=StrategyStatus.TESTING,
                tags=", ".join(metadata.tags) or None,
                library_strategy_id=definition.id,
            )
            try:
                self.strategy_repo.add(container)
                self.session.commit()
            except IntegrityError as exc:
                self.session.rollback()
                last_error = exc
                raced = self.strategy_repo.get_by_library_strategy_id(definition.id)
                if raced is not None:
                    return raced
                # Another row took this name (often a soft-deleted container). Try
                # the next free variant on the next loop iteration.
                preferred = name
                continue
            self.session.refresh(container)
            return container

        if last_error is not None:
            raise last_error
        raise ValidationError(
            f"Could not allocate a unique research container name for '{metadata.name}'"
        )

    def _available_container_name(self, preferred: str) -> str:
        """``preferred``, or the first free variant of it.

        ``strategies.name`` is unique, and a user is perfectly entitled to have
        already named an idea "Opening Range Breakout". Soft-deleted rows still
        reserve their names at the database level.
        """
        if not self.strategy_repo.is_name_taken(preferred):
            return preferred
        for attempt in range(2, MAX_CONTAINER_NAME_ATTEMPTS + 2):
            candidate = f"{preferred} (Library {attempt})"
            if not self.strategy_repo.is_name_taken(candidate):
                return candidate
        raise ValidationError(
            f"Could not find a free container name for '{preferred}' after "
            f"{MAX_CONTAINER_NAME_ATTEMPTS} attempts"
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
            row_count=version.row_count,
        )

    def _load_source(self, strategy_id: str) -> str:
        if self.strategy_repo.get(strategy_id) is None:
            raise NotFoundError(f"Strategy '{strategy_id}' not found")

        code = self.code_repo.get_by_strategy_id(strategy_id)
        if code is None or not code.code.strip():
            raise ValidationError("This strategy has no code saved yet")
        return code.code
