"""Strategy persistence. SQL queries only - no business rules (ARCHITECTURE.md 2.1)."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.domain.enums import Priority, StrategyStatus
from app.models.strategy import Strategy


class StrategyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _active(self) -> Select[tuple[Strategy]]:
        return select(Strategy).where(Strategy.deleted_at.is_(None))

    def get(self, strategy_id: str) -> Strategy | None:
        return self.session.scalars(self._active().where(Strategy.id == strategy_id)).first()

    def get_by_name(self, name: str) -> Strategy | None:
        return self.session.scalars(self._active().where(Strategy.name == name)).first()

    def get_by_library_strategy_id(self, library_strategy_id: str) -> Strategy | None:
        """The research container holding runs of one built-in strategy, if any."""
        stmt = (
            self._active()
            .where(Strategy.library_strategy_id == library_strategy_id)
            .order_by(Strategy.created_at.asc())
        )
        return self.session.scalars(stmt).first()

    def search(
        self,
        *,
        q: str | None,
        status: str | None,
        sort_column: str,
        descending: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Strategy], int]:
        stmt = self._active()
        if q:
            stmt = stmt.where(Strategy.name.ilike(f"%{q}%"))
        if status:
            stmt = stmt.where(Strategy.status == status)

        column = Strategy.updated_at if sort_column == "updated_at" else Strategy.name
        stmt = stmt.order_by(column.desc() if descending else column.asc())

        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(self.session.scalars(stmt.limit(limit).offset(offset)))
        return items, total

    def add(self, strategy: Strategy) -> Strategy:
        self.session.add(strategy)
        self.session.flush()
        return strategy

    def counts_by_status(self) -> dict[str, int]:
        stmt = (
            select(Strategy.status, func.count())
            .where(Strategy.deleted_at.is_(None))
            .group_by(Strategy.status)
        )
        return dict(self.session.execute(stmt).tuples().all())

    def recently_updated(self, limit: int) -> list[Strategy]:
        stmt = self._active().order_by(Strategy.updated_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    def high_priority(self, limit: int) -> list[Strategy]:
        stmt = (
            self._active()
            .where(Strategy.priority == Priority.HIGH)
            .order_by(Strategy.updated_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def needs_review(self, limit: int) -> list[Strategy]:
        """Strategies actively being tested, oldest-reviewed first."""
        stmt = (
            self._active()
            .where(Strategy.status == StrategyStatus.TESTING)
            .order_by(Strategy.updated_at.asc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))
