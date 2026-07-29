"""Strategy code persistence. SQL queries only - no business rules (ARCHITECTURE.md 2.1)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.strategy_code import StrategyCode


class StrategyCodeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_strategy_id(self, strategy_id: str) -> StrategyCode | None:
        stmt = select(StrategyCode).where(StrategyCode.strategy_id == strategy_id)
        return self.session.scalars(stmt).first()

    def add(self, strategy_code: StrategyCode) -> StrategyCode:
        self.session.add(strategy_code)
        self.session.flush()
        return strategy_code
