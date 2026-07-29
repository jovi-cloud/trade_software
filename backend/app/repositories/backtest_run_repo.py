"""BacktestRun persistence. SQL queries only — no business rules."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.backtest import BacktestRun
from app.models.dataset import Dataset
from app.models.strategy import Strategy


class BacktestRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _base_stmt(self) -> Select[tuple[BacktestRun, str, str]]:
        return (
            select(BacktestRun, Strategy.name, Dataset.name)
            .join(Strategy, BacktestRun.strategy_id == Strategy.id)
            .join(Dataset, BacktestRun.dataset_id == Dataset.id)
        )

    def get(self, run_id: str) -> tuple[BacktestRun, str, str] | None:
        row = self.session.execute(self._base_stmt().where(BacktestRun.id == run_id)).first()
        if row is None:
            return None
        run, strategy_name, dataset_name = row._tuple()
        return run, strategy_name, dataset_name

    def add(self, run: BacktestRun) -> BacktestRun:
        self.session.add(run)
        self.session.flush()
        return run

    def delete(self, run: BacktestRun) -> None:
        self.session.delete(run)

    def search(
        self,
        *,
        q: str | None,
        strategy_id: str | None,
        dataset_id: str | None,
        status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        sort_column: str,
        descending: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[BacktestRun, str, str]], int]:
        stmt = self._base_stmt()
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Strategy.name.ilike(like),
                    Dataset.name.ilike(like),
                    BacktestRun.id.ilike(like),
                    BacktestRun.experiment_name.ilike(like),
                    BacktestRun.hypothesis.ilike(like),
                    BacktestRun.tags.ilike(like),
                )
            )
        if strategy_id:
            stmt = stmt.where(BacktestRun.strategy_id == strategy_id)
        if dataset_id:
            stmt = stmt.where(BacktestRun.dataset_id == dataset_id)
        if status:
            stmt = stmt.where(BacktestRun.status == status)
        if date_from is not None:
            stmt = stmt.where(BacktestRun.execution_completed_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(BacktestRun.execution_completed_at <= date_to)

        sort_columns = {
            "created_at": BacktestRun.created_at,
            "execution_completed_at": BacktestRun.execution_completed_at,
            "trade_count": BacktestRun.trade_count,
            "net_profit": func.json_extract(BacktestRun.metrics_json, "$.net_profit"),
        }
        column = sort_columns.get(sort_column, BacktestRun.execution_completed_at)
        stmt = stmt.order_by(column.desc() if descending else column.asc())

        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = [row._tuple() for row in self.session.execute(stmt.limit(limit).offset(offset))]
        return rows, total
