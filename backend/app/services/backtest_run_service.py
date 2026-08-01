"""Persist and retrieve immutable backtest run records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.analytics import AnalyticsReport
from app.analytics.serialize import report_from_json
from app.core.exceptions import NotFoundError, ValidationError
from app.core.hashing import hash_file, hash_text
from app.core.paths import DataPaths
from app.db.base import utcnow
from app.domain.enums import BacktestRunStatus, DatasetVersionStatus
from app.engine.explain.serialize import event_to_dict
from app.engine.results.metrics import MetricsEngine
from app.engine.results.result import ExecutionResult
from app.engine.runner import ExecutionConfig
from app.engine.version import ENGINE_VERSION
from app.models.backtest import BacktestRun
from app.repositories.backtest_run_repo import BacktestRunRepository
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.dataset_version_repo import DatasetVersionRepository
from app.repositories.strategy_code_repo import StrategyCodeRepository
from app.repositories.strategy_repo import StrategyRepository
from app.schemas.analytics import AnalyticsReportRead, analytics_report_read
from app.schemas.backtest_run import BacktestRunResearchUpdate
from app.services.analytics_service import AnalyticsService
from app.services.execution_service import ResolvedDatasetVersion

#: Sortable columns for the runs list. The analytics headline metrics are real
#: columns (ARCHITECTURE.md 3.2), so sorting by Sharpe costs one index seek
#: rather than parsing a JSON blob per row.
ALLOWED_SORT_COLUMNS = {
    "created_at",
    "execution_completed_at",
    "net_profit",
    "trade_count",
    "total_return_pct",
    "cagr_pct",
    "max_drawdown_pct",
    "sharpe",
    "sortino",
    "calmar",
    "profit_factor",
    "win_rate_pct",
    "expectancy",
    "exposure_pct",
}
MAX_PAGE_SIZE = 100
RESEARCH_TEXT_FIELDS = (
    "experiment_name",
    "hypothesis",
    "what_changed",
    "expected_result",
    "actual_result",
    "conclusion",
    "next_experiment",
    "notes",
)


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_tags(tags: str | None) -> str | None:
    if not tags:
        return None
    seen: dict[str, None] = {}
    for part in tags.split(","):
        cleaned = part.strip()
        if cleaned:
            seen.setdefault(cleaned, None)
    return ", ".join(seen) or None


def _json_dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _serialize_result(result: ExecutionResult, *, initial_capital: float) -> dict[str, object]:
    metrics = result.metrics
    if metrics is None:
        metrics, _ = MetricsEngine().compute(
            trades=list(result.trades),
            initial_capital=initial_capital,
            final_cash=result.final_cash,
        )
    return {
        "metrics": asdict(metrics),
        "equity_history": [asdict(point) for point in result.equity_history],
        "entry_markers": [asdict(marker) for marker in result.entry_markers],
        "exit_markers": [asdict(marker) for marker in result.exit_markers],
        "trailing_stop_points": [asdict(point) for point in result.trailing_stop_points],
        "candles": [asdict(candle) for candle in result.candles],
        "orders": [asdict(order) for order in result.orders],
        "trades": [asdict(trade) for trade in result.trades],
        "strategy_logs": list(result.strategy_logs),
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "explain_events": [event_to_dict(event) for event in result.explain_events],
        "explain_level": result.explain_level.value,
    }


def _headline_columns(report: AnalyticsReport) -> dict[str, float | None]:
    """The denormalised subset of the report that lives in real columns.

    Mapped explicitly rather than by name-matching so a rename in the analytics
    layer cannot silently blank a column the runs list sorts on.
    """
    return {
        "total_return_pct": report.returns.total_return_pct,
        "cagr_pct": report.returns.cagr_pct,
        "max_drawdown_pct": report.risk.max_drawdown_pct,
        "sharpe": report.risk_adjusted.sharpe_ratio,
        "sortino": report.risk_adjusted.sortino_ratio,
        "calmar": report.risk_adjusted.calmar_ratio,
        "profit_factor": report.returns.profit_factor,
        "win_rate_pct": report.trades.win_rate_pct,
        "expectancy": report.returns.expectancy,
        "exposure_pct": report.risk.exposure_pct,
    }


class BacktestRunService:
    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.repo = BacktestRunRepository(session)
        self.analytics = AnalyticsService()
        self.strategy_repo = StrategyRepository(session)
        self.code_repo = StrategyCodeRepository(session)
        self.dataset_repo = DatasetRepository(session)
        self.version_repo = DatasetVersionRepository(session)

    def create_from_execution(
        self,
        *,
        strategy_id: str,
        dataset_id: str,
        config: ExecutionConfig,
        result: ExecutionResult,
        started_at: datetime,
        strategy_snapshot: str | None = None,
        library_strategy_id: str | None = None,
        library_strategy_version: str | None = None,
        strategy_params: Mapping[str, object] | None = None,
        dataset_version: ResolvedDatasetVersion | None = None,
        analytics: AnalyticsReport | None = None,
        run_id: str | None = None,
    ) -> BacktestRun:
        """Persist one completed replay.

        ``run_id`` must be supplied whenever the execution wrote a decision log,
        and must be the same id the log was written under - the artifact lives at
        ``artifacts/{run_id}/decisions.parquet`` and is located by convention, not
        by a stored path.

        ``strategy_snapshot`` overrides what is recorded as the code that ran.
        It is supplied for a library-strategy run, where the reproducibility
        record is a pinned id, version and parameter set rather than source
        text. Omitted, the saved code is snapshotted exactly as before.

        The ``library_*`` fields record the same pinning as columns, so the
        result screen can link back to the library entry and re-run it without
        parsing the snapshot text.

        ``analytics`` is the performance and risk report for this run. Passed in
        rather than computed here so the caller that already needed it for its
        response does not pay for it twice. Omitted, it is computed from the
        result - a run is never stored without its report.
        """
        strategy = self.strategy_repo.get(strategy_id)
        if strategy is None:
            raise NotFoundError(f"Strategy '{strategy_id}' not found")

        snapshot = strategy_snapshot
        if snapshot is None:
            code = self.code_repo.get_by_strategy_id(strategy_id)
            if code is None or not code.code.strip():
                raise ValidationError("This strategy has no code saved yet")
            snapshot = code.code

        dataset = self.dataset_repo.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset '{dataset_id}' not found")

        if dataset_version is None:
            if dataset.current_version_id is None:
                raise ValidationError(
                    f"Dataset '{dataset.name}' has no valid version to run against"
                )
            orm_version = self.version_repo.get(dataset.current_version_id)
            if orm_version is None or orm_version.status != DatasetVersionStatus.VALID.value:
                raise ValidationError(
                    f"Dataset '{dataset.name}' is not ready to run against "
                    f"(version status: {orm_version.status if orm_version else 'missing'})"
                )
            parquet_path = self.paths.root / orm_version.file_path
            version = ResolvedDatasetVersion(
                id=orm_version.id,
                version_number=orm_version.version_number,
                parquet_path=parquet_path,
                fingerprint=orm_version.fingerprint,
                quality_score=orm_version.quality_score,
                data_import_id=orm_version.data_import_id,
                imported_at=orm_version.created_at,
                row_count=orm_version.row_count,
            )
        else:
            version = dataset_version
            parquet_path = version.parquet_path

        if not parquet_path.exists():
            raise NotFoundError(f"The stored bars for dataset '{dataset.name}' are missing")

        data_import = None
        if version.data_import_id:
            from app.repositories.data_import_repo import DataImportRepository

            data_import = DataImportRepository(self.session).get(version.data_import_id)

        completed_at = utcnow()
        payload = _serialize_result(result, initial_capital=config.initial_capital)
        report = analytics or self.analytics.analyse_result(
            result, initial_capital=config.initial_capital
        )
        status = BacktestRunStatus.COMPLETED if result.completed else BacktestRunStatus.FAILED
        error_message = "; ".join(result.errors) if result.errors else None

        run = BacktestRun(
            **({} if run_id is None else {"id": run_id}),
            strategy_id=strategy_id,
            dataset_id=dataset_id,
            dataset_version_id=version.id,
            dataset_version_number=version.version_number,
            dataset_import_id=version.data_import_id,
            dataset_imported_at=version.imported_at
            or (data_import.created_at if data_import else None),
            dataset_quality_score=version.quality_score,
            engine_version=ENGINE_VERSION,
            execution_started_at=started_at,
            execution_completed_at=completed_at,
            execution_time_ms=result.execution_time_ms,
            initial_capital=config.initial_capital,
            commission=config.commission,
            slippage=config.slippage,
            strategy_code_snapshot=snapshot,
            dataset_hash=version.fingerprint or hash_file(parquet_path),
            strategy_hash=hash_text(snapshot),
            library_strategy_id=library_strategy_id,
            library_strategy_version=library_strategy_version,
            strategy_params_json=(
                None if strategy_params is None else _json_dumps(dict(strategy_params))
            ),
            bars_processed=result.bars_processed,
            trade_count=result.trade_count,
            final_cash=result.final_cash,
            position_closed=result.position_closed,
            metrics_json=_json_dumps(payload["metrics"]),
            analytics_json=AnalyticsService.to_json(report),
            equity_history_json=_json_dumps(payload["equity_history"]),
            entry_markers_json=_json_dumps(payload["entry_markers"]),
            exit_markers_json=_json_dumps(payload["exit_markers"]),
            trailing_stop_points_json=_json_dumps(payload["trailing_stop_points"]),
            candles_json=_json_dumps(payload["candles"]),
            orders_json=_json_dumps(payload["orders"]),
            trades_json=_json_dumps(payload["trades"]),
            strategy_logs_json=_json_dumps(payload["strategy_logs"]),
            warnings_json=_json_dumps(payload["warnings"]),
            errors_json=_json_dumps(payload["errors"]),
            explain_events_json=_json_dumps(payload["explain_events"]),
            explain_level=str(payload["explain_level"]),
            decision_log_rows=result.decision_rows,
            decision_schema_json=(
                None
                if result.decision_schema is None
                else _json_dumps(result.decision_schema.to_dict())
            ),
            status=status,
            error_message=error_message,
            **_headline_columns(report),
        )
        self.repo.add(run)
        self.session.commit()
        return run

    def create_failed(
        self,
        *,
        strategy_id: str,
        dataset_id: str,
        config: ExecutionConfig,
        started_at: datetime,
        strategy_code: str,
        dataset_path: Path,
        error_message: str,
        execution_time_ms: float = 0.0,
        dataset_version_id: str | None = None,
        dataset_version_number: int | None = None,
        dataset_import_id: str | None = None,
        dataset_imported_at: datetime | None = None,
        dataset_quality_score: int | None = None,
        dataset_fingerprint: str | None = None,
    ) -> BacktestRun:
        completed_at = utcnow()
        empty_metrics = asdict(
            MetricsEngine().compute(
                trades=[],
                initial_capital=config.initial_capital,
                final_cash=config.initial_capital,
            )[0]
        )
        run = BacktestRun(
            strategy_id=strategy_id,
            dataset_id=dataset_id,
            dataset_version_id=dataset_version_id,
            dataset_version_number=dataset_version_number,
            dataset_import_id=dataset_import_id,
            dataset_imported_at=dataset_imported_at,
            dataset_quality_score=dataset_quality_score,
            engine_version=ENGINE_VERSION,
            execution_started_at=started_at,
            execution_completed_at=completed_at,
            execution_time_ms=execution_time_ms,
            initial_capital=config.initial_capital,
            commission=config.commission,
            slippage=config.slippage,
            strategy_code_snapshot=strategy_code,
            dataset_hash=dataset_fingerprint or hash_file(dataset_path),
            strategy_hash=hash_text(strategy_code),
            bars_processed=0,
            trade_count=0,
            final_cash=config.initial_capital,
            position_closed=True,
            metrics_json=_json_dumps(empty_metrics),
            equity_history_json="[]",
            entry_markers_json="[]",
            exit_markers_json="[]",
            candles_json="[]",
            orders_json="[]",
            trades_json="[]",
            strategy_logs_json="[]",
            warnings_json="[]",
            errors_json=_json_dumps([error_message]),
            explain_events_json="[]",
            explain_level="trades_only",
            status=BacktestRunStatus.FAILED,
            error_message=error_message,
        )
        self.repo.add(run)
        self.session.commit()
        return run

    def get(self, run_id: str) -> tuple[BacktestRun, str, str, str]:
        row = self.repo.get(run_id)
        if row is None:
            raise NotFoundError(f"Backtest run '{run_id}' not found")
        return row

    def analytics_report_for(self, run: BacktestRun) -> AnalyticsReport:
        """The run's analytics as the engine-side dataclass."""
        if run.analytics_json:
            try:
                return report_from_json(run.analytics_json)
            except (PydanticValidationError, KeyError, TypeError, ValueError):
                pass

        report = self.analytics.analyse_snapshot(
            trades=json.loads(run.trades_json),
            candles=json.loads(run.candles_json),
            initial_capital=run.initial_capital,
        )
        run.analytics_json = AnalyticsService.to_json(report)
        for column, value in _headline_columns(report).items():
            setattr(run, column, value)
        self.session.commit()
        return report

    def analytics_for(self, run: BacktestRun) -> AnalyticsReportRead:
        """The run's performance and risk report.

        Normally a straight read of the stored snapshot. For a run recorded
        before analytics existed - or one whose stored report no longer matches
        the current schema - the report is rebuilt from the trades and candles
        that run already saved, then written back along with the headline
        columns.

        That write-back is a cache fill, not a mutation of history: the execution
        snapshot (trades, orders, candles, events) is never touched, and the
        rebuilt report is exactly what those immutable inputs produce. Without it
        an old run would stay unsortable in the runs list forever.
        """
        return analytics_report_read(self.analytics_report_for(run))

    def list(
        self,
        *,
        q: str | None,
        strategy_id: str | None,
        dataset_id: str | None,
        status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        sort: str,
        order: str,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[BacktestRun, str, str]], int]:
        if sort not in ALLOWED_SORT_COLUMNS:
            raise ValidationError(f"Invalid sort column '{sort}'")
        if limit > MAX_PAGE_SIZE:
            raise ValidationError(f"limit must be at most {MAX_PAGE_SIZE}")

        descending = order == "desc"
        return self.repo.search(
            q=q,
            strategy_id=strategy_id,
            dataset_id=dataset_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            sort_column=sort,
            descending=descending,
            limit=limit,
            offset=offset,
        )

    def update_research(self, run_id: str, data: BacktestRunResearchUpdate) -> BacktestRun:
        row = self.repo.get(run_id)
        if row is None:
            raise NotFoundError(f"Backtest run '{run_id}' not found")
        run = row[0]

        updates = data.model_dump(exclude_unset=True)
        for field in RESEARCH_TEXT_FIELDS:
            if field in updates:
                setattr(run, field, _clean_text(updates[field]))
        if "tags" in updates:
            run.tags = _normalize_tags(updates["tags"])
        if "rating" in updates:
            run.rating = updates["rating"]

        run.updated_at = utcnow()
        self.session.commit()
        return run

    def delete(self, run_id: str) -> None:
        row = self.repo.get(run_id)
        if row is None:
            raise NotFoundError(f"Backtest run '{run_id}' not found")
        self.repo.delete(row[0])
        self.session.commit()

    @staticmethod
    def parse_date_filter(value: str | None, *, end_of_day: bool = False) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError as exc:
            raise ValidationError("date filters must use YYYY-MM-DD") from exc
        if end_of_day:
            return parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
        return parsed
