"""Build a downloadable ZIP archive of one backtest run's complete results."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.paths import DataPaths
from app.data import decision_store
from app.repositories.backtest_run_repo import BacktestRunRepository
from app.schemas.backtest_run import read_from_row
from app.services.backtest_run_service import BacktestRunService
from app.services.explain_service import ExplainService

_README = """Backtest run export
===================

This archive contains everything needed to review or re-analyse one backtest run
outside the application.

Files
-----
run.json              Full run snapshot (config, metrics, analytics, research)
strategy_code.py      Strategy source used for this run
candles.csv           OHLCV bars (price chart data)
equity_curve.csv      Analytics equity curve (chart data)
drawdown_curve.csv    Analytics drawdown curve (chart data)
equity_history.csv    Per-trade equity points
entry_markers.csv     Trade entry markers for the price chart
exit_markers.csv      Trade exit markers for the price chart
trades.csv            Closed trades
orders.csv            Orders submitted during the run
metrics.csv           Flat performance metrics
analytics_metrics.csv All analytics metrics with labels
monthly_returns.csv   Monthly return table
yearly_returns.csv    Yearly return table
lifecycle_events.json System lifecycle events
explain_events.json   Full explain event log (when recorded)
decision_summary.json Condition funnel summary (when a decision log exists)
decisions.parquet     Per-bar decision log (when recorded)
warnings.txt          Engine warnings
errors.txt            Engine errors
strategy_logs.txt     Strategy log lines
"""


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, indent=2, default=str).encode("utf-8")


def _dict_rows_to_csv(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _models_to_csv(models: list[BaseModel]) -> bytes:
    if not models:
        return b""
    return _dict_rows_to_csv([model.model_dump(mode="json") for model in models])


def _lines_to_bytes(lines: list[str]) -> bytes:
    return "\n".join(lines).encode("utf-8")


class RunExportService:
    """Package a persisted run into a single ZIP download."""

    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.repo = BacktestRunRepository(session)
        self.backtest_runs = BacktestRunService(session, paths)
        self.explain = ExplainService(session, paths)

    def build_zip(self, run_id: str) -> tuple[bytes, str]:
        row = self.repo.get(run_id)
        if row is None:
            raise NotFoundError(f"Backtest run '{run_id}' not found")
        run, strategy_name, dataset_name, dataset_timezone = row
        analytics = self.backtest_runs.analytics_for(run)
        detail = read_from_row(
            run,
            strategy_name,
            dataset_name,
            dataset_timezone=dataset_timezone,
            analytics=analytics,
        )

        stamp = run.execution_completed_at.astimezone(UTC).strftime("%Y%m%d")
        safe_strategy = "".join(
            char if char.isalnum() or char in "-_" else "_" for char in strategy_name
        )[:40]
        filename = f"backtest_{safe_strategy}_{stamp}_{run_id[:8]}.zip"

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("README.txt", _README)
            archive.writestr("run.json", _json_bytes(detail.model_dump(mode="json")))
            archive.writestr("strategy_code.py", run.strategy_code_snapshot)
            archive.writestr("candles.csv", _models_to_csv(detail.candles))
            archive.writestr("equity_curve.csv", _models_to_csv(analytics.series.equity_curve))
            archive.writestr("drawdown_curve.csv", _models_to_csv(analytics.series.drawdown_curve))
            archive.writestr("equity_history.csv", _models_to_csv(detail.equity_history))
            archive.writestr("entry_markers.csv", _models_to_csv(detail.entry_markers))
            archive.writestr("exit_markers.csv", _models_to_csv(detail.exit_markers))
            archive.writestr("trades.csv", _models_to_csv(detail.trades))
            archive.writestr("orders.csv", _models_to_csv(detail.orders))
            archive.writestr(
                "metrics.csv",
                _dict_rows_to_csv([detail.metrics.model_dump(mode="json")]),
            )
            archive.writestr(
                "analytics_metrics.csv",
                _dict_rows_to_csv([metric.model_dump(mode="json") for metric in analytics.metrics]),
            )
            archive.writestr(
                "monthly_returns.csv",
                _models_to_csv(analytics.series.monthly_returns),
            )
            archive.writestr(
                "yearly_returns.csv",
                _models_to_csv(analytics.series.yearly_returns),
            )
            archive.writestr(
                "lifecycle_events.json",
                _json_bytes([event.model_dump(mode="json") for event in detail.lifecycle_events]),
            )
            archive.writestr("explain_events.json", run.explain_events_json.encode("utf-8"))
            archive.writestr("warnings.txt", _lines_to_bytes(detail.warnings))
            archive.writestr("errors.txt", _lines_to_bytes(detail.errors))
            archive.writestr("strategy_logs.txt", _lines_to_bytes(detail.strategy_logs))

            decisions_path = self.paths.run_decisions_parquet(run_id)
            if decision_store.log_exists(decisions_path):
                archive.write(decisions_path, arcname="decisions.parquet")
                try:
                    summary = self.explain.get_decision_summary(run_id)
                    archive.writestr(
                        "decision_summary.json",
                        _json_bytes(summary.model_dump(mode="json")),
                    )
                except NotFoundError:
                    pass

        return buffer.getvalue(), filename
