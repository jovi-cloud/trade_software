"""Background handler for backtest execution jobs."""

from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.exceptions import AppError, JobCancelledError
from app.core.paths import get_data_paths
from app.db.session import session_scope
from app.jobs.store import InMemoryJobStore
from app.schemas.backtest import BacktestExecuteRequest
from app.services.backtest_job_service import BacktestJobService

logger = logging.getLogger(__name__)


def run_backtest_job(
    job_id: str,
    payload: dict[str, Any],
    *,
    settings: Settings,
    store: InMemoryJobStore,
    session_factory: sessionmaker[Session] | None = None,
) -> None:
    """Execute one backtest off the request thread and persist progress updates."""
    # Lower priority so the UI and other API calls stay responsive on a laptop.
    try:
        if hasattr(os, "nice"):
            os.nice(5)
    except OSError:
        pass

    store.mark_running(job_id)
    store.update_progress(
        job_id,
        progress_pct=2.0,
        progress_message="Preparing backtest…",
    )

    try:
        request = BacktestExecuteRequest.model_validate(payload)
        paths = get_data_paths(settings)

        def on_progress(*, bars_processed: int, total_bars: int, phase: str) -> None:
            if phase == "loading":
                store.update_progress(
                    job_id,
                    progress_pct=5.0,
                    progress_message="Loading market data…",
                    total_bars=total_bars,
                )
                return
            if phase == "analytics":
                store.update_progress(
                    job_id,
                    progress_pct=90.0,
                    progress_message="Computing analytics…",
                    bars_processed=bars_processed,
                    total_bars=total_bars,
                )
                return
            if phase == "persist":
                store.update_progress(
                    job_id,
                    progress_pct=95.0,
                    progress_message="Saving results…",
                    bars_processed=bars_processed,
                    total_bars=total_bars,
                )
                return

            engine_pct = 10.0 + (bars_processed / total_bars * 75.0) if total_bars else 10.0
            store.update_progress(
                job_id,
                progress_pct=engine_pct,
                progress_message=f"Processing bar {bars_processed:,} of {total_bars:,}",
                bars_processed=bars_processed,
                total_bars=total_bars,
            )

        with session_scope(session_factory) as session:
            result = BacktestJobService(session, paths).run(
                request,
                on_progress=on_progress,
                should_cancel=lambda: store.is_cancel_requested(job_id),
            )

        store.mark_completed(job_id, result=result)
    except JobCancelledError:
        logger.info("Backtest job %s cancelled", job_id)
        store.mark_cancelled(job_id)
    except AppError as exc:
        logger.warning("Backtest job %s failed: %s", job_id, exc.message)
        store.mark_failed(job_id, error_message=exc.message)
    except Exception:
        logger.exception("Backtest job %s failed unexpectedly", job_id)
        store.mark_failed(
            job_id,
            error_message="An unexpected error occurred while running the backtest.",
        )
