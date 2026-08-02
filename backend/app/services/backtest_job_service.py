"""Backtest execution orchestration for background jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.analytics import AnalyticsConfig
from app.core.exceptions import JobCancelledError
from app.core.paths import DataPaths
from app.db.base import utcnow
from app.schemas.backtest import BacktestExecuteRequest, BacktestJobResultRead
from app.services.analytics_service import AnalyticsService
from app.services.backtest_run_service import BacktestRunService
from app.services.execution_service import ExecutionService

ProgressCallback = Callable[..., None]
CancelCallback = Callable[[], bool]


class BacktestJobService:
    """Run and persist one backtest, reporting progress to the job store."""

    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.execution_service = ExecutionService(session, paths)
        self.run_service = BacktestRunService(session, paths)

    def run(
        self,
        payload: BacktestExecuteRequest,
        *,
        on_progress: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
    ) -> dict[str, Any]:
        plan = self.execution_service.plan(
            dataset_id=payload.dataset_id,
            strategy_id=payload.strategy_id,
            library_strategy_id=payload.library_strategy_id,
            strategy_params=payload.strategy_params,
            initial_capital=payload.initial_capital,
            commission=payload.commission,
            slippage=payload.slippage,
            explain_level=payload.explain_level,
            dataset_version_id=payload.dataset_version_id,
            dataset_version_number=payload.dataset_version_number,
            skip_trades_on_price_anomaly_days=payload.skip_trades_on_price_anomaly_days,
            skip_trades_on_intraday_anomalies_10pct=payload.skip_trades_on_intraday_anomalies_10pct,
            skip_trades_on_intraday_anomalies_20pct=payload.skip_trades_on_intraday_anomalies_20pct,
            skip_trades_on_cross_day_anomalies_10pct=payload.skip_trades_on_cross_day_anomalies_10pct,
            skip_trades_on_cross_day_anomalies_20pct=payload.skip_trades_on_cross_day_anomalies_20pct,
            max_trades_per_day=payload.max_trades_per_day,
            entry_window_start=payload.entry_window_start,
            entry_window_end=payload.entry_window_end,
            override_stop_loss=payload.override_stop_loss,
            stop_loss_override_mode=payload.stop_loss_override_mode,
            stop_loss_value=payload.stop_loss_value,
            enable_session_exit=payload.enable_session_exit,
            session_exit_at=payload.session_exit_at,
        )
        started_at = utcnow()

        def report_progress(
            *,
            bars_processed: int = 0,
            total_bars: int = 0,
            phase: str = "engine",
        ) -> None:
            if on_progress is None:
                return
            on_progress(bars_processed=bars_processed, total_bars=total_bars, phase=phase)

        def check_cancelled() -> None:
            if should_cancel is not None and should_cancel():
                raise JobCancelledError("Backtest cancelled")

        check_cancelled()
        result = self.execution_service.execute(
            strategy_id=plan.strategy_id,
            dataset_id=plan.dataset_id,
            config=plan.config,
            strategy=plan.strategy,
            dataset_version=plan.dataset_version,
            on_progress=report_progress,
            should_cancel=should_cancel,
            max_bars=payload.max_bars,
            run_id=plan.run_id,
        )
        check_cancelled()
        report_progress(
            phase="analytics",
            bars_processed=result.bars_processed,
            total_bars=result.bars_processed,
        )
        report = AnalyticsService().analyse_result(
            result,
            initial_capital=plan.config.initial_capital,
            config=AnalyticsConfig(session_timezone=plan.config.session_timezone),
        )
        check_cancelled()
        report_progress(
            phase="persist",
            bars_processed=result.bars_processed,
            total_bars=result.bars_processed,
        )
        run = self.run_service.create_from_execution(
            strategy_id=plan.strategy_id,
            dataset_id=plan.dataset_id,
            config=plan.config,
            result=result,
            started_at=started_at,
            strategy_snapshot=plan.strategy.snapshot,
            library_strategy_id=plan.strategy.library_strategy_id,
            library_strategy_version=plan.strategy.library_strategy_version,
            strategy_params=plan.strategy.params or None,
            dataset_version=plan.dataset_version,
            analytics=report,
            # Must match the id the decision log was streamed under.
            run_id=plan.run_id,
        )
        # A receipt, not the replay. The full result is on the run, which the
        # caller reads once by id - rather than through every progress poll.
        receipt = BacktestJobResultRead(
            run_id=run.id,
            dataset_version_id=plan.dataset_version.id,
            dataset_version_number=plan.dataset_version.version_number,
            dataset_fingerprint=plan.dataset_version.fingerprint,
            completed=result.completed,
            bars_processed=result.bars_processed,
            execution_time_ms=result.execution_time_ms,
            trade_count=result.trade_count,
            final_cash=result.final_cash,
            position_closed=result.position_closed,
            explain_level=result.explain_level,
            warnings=list(result.warnings),
            errors=list(result.errors),
        )
        return receipt.model_dump(mode="json")
