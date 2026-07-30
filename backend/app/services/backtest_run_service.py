"""Persist and retrieve immutable backtest run records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.hashing import hash_file, hash_text
from app.core.paths import DataPaths
from app.db.base import utcnow
from app.domain.enums import BacktestRunStatus, ImportStatus
from app.engine.explain.serialize import event_to_dict
from app.engine.results.metrics import MetricsEngine
from app.engine.results.result import ExecutionResult
from app.engine.runner import ExecutionConfig
from app.engine.version import ENGINE_VERSION
from app.models.backtest import BacktestRun
from app.repositories.backtest_run_repo import BacktestRunRepository
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.strategy_code_repo import StrategyCodeRepository
from app.repositories.strategy_repo import StrategyRepository
from app.schemas.backtest_run import BacktestRunResearchUpdate

ALLOWED_SORT_COLUMNS = {
    "created_at",
    "execution_completed_at",
    "net_profit",
    "trade_count",
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
        "candles": [asdict(candle) for candle in result.candles],
        "orders": [asdict(order) for order in result.orders],
        "trades": [asdict(trade) for trade in result.trades],
        "strategy_logs": list(result.strategy_logs),
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "explain_events": [event_to_dict(event) for event in result.explain_events],
        "explain_level": result.explain_level.value,
    }


class BacktestRunService:
    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.repo = BacktestRunRepository(session)
        self.strategy_repo = StrategyRepository(session)
        self.code_repo = StrategyCodeRepository(session)
        self.dataset_repo = DatasetRepository(session)

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
    ) -> BacktestRun:
        """Persist one completed replay.

        ``strategy_snapshot`` overrides what is recorded as the code that ran.
        It is supplied for a library-strategy run, where the reproducibility
        record is a pinned id, version and parameter set rather than source
        text. Omitted, the saved code is snapshotted exactly as before.

        The ``library_*`` fields record the same pinning as columns, so the
        result screen can link back to the library entry and re-run it without
        parsing the snapshot text.
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
        if dataset.import_status != ImportStatus.COMPLETED:
            raise ValidationError(
                f"Dataset '{dataset.name}' is not ready to run against "
                f"(import status: {dataset.import_status})"
            )

        parquet_path = self.paths.root / dataset.file_path
        if not parquet_path.exists():
            raise NotFoundError(f"The stored bars for dataset '{dataset.name}' are missing")

        completed_at = utcnow()
        payload = _serialize_result(result, initial_capital=config.initial_capital)
        status = BacktestRunStatus.COMPLETED if result.completed else BacktestRunStatus.FAILED
        error_message = "; ".join(result.errors) if result.errors else None

        run = BacktestRun(
            strategy_id=strategy_id,
            dataset_id=dataset_id,
            engine_version=ENGINE_VERSION,
            execution_started_at=started_at,
            execution_completed_at=completed_at,
            execution_time_ms=result.execution_time_ms,
            initial_capital=config.initial_capital,
            commission=config.commission,
            slippage=config.slippage,
            strategy_code_snapshot=snapshot,
            dataset_hash=hash_file(parquet_path),
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
            equity_history_json=_json_dumps(payload["equity_history"]),
            entry_markers_json=_json_dumps(payload["entry_markers"]),
            exit_markers_json=_json_dumps(payload["exit_markers"]),
            candles_json=_json_dumps(payload["candles"]),
            orders_json=_json_dumps(payload["orders"]),
            trades_json=_json_dumps(payload["trades"]),
            strategy_logs_json=_json_dumps(payload["strategy_logs"]),
            warnings_json=_json_dumps(payload["warnings"]),
            errors_json=_json_dumps(payload["errors"]),
            explain_events_json=_json_dumps(payload["explain_events"]),
            explain_level=str(payload["explain_level"]),
            status=status,
            error_message=error_message,
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
            engine_version=ENGINE_VERSION,
            execution_started_at=started_at,
            execution_completed_at=completed_at,
            execution_time_ms=execution_time_ms,
            initial_capital=config.initial_capital,
            commission=config.commission,
            slippage=config.slippage,
            strategy_code_snapshot=strategy_code,
            dataset_hash=hash_file(dataset_path),
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

    def get(self, run_id: str) -> tuple[BacktestRun, str, str]:
        row = self.repo.get(run_id)
        if row is None:
            raise NotFoundError(f"Backtest run '{run_id}' not found")
        return row

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
