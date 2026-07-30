"""Library container naming when soft-deleted rows reserve names."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.paths import get_data_paths
from app.domain.enums import MarketType, Priority, StrategyStatus, Timeframe
from app.models.strategy import Strategy
from app.repositories.strategy_repo import StrategyRepository
from app.services.execution_service import ExecutionService
from tests.api.test_library_backtest_flow import LIBRARY_STRATEGY_ID


def test_soft_deleted_name_does_not_block_library_container(
    db_session: Session, settings: Settings
) -> None:
    """A soft-deleted strategy still occupies its name in SQLite."""
    repo = StrategyRepository(db_session)
    deleted = Strategy(
        name="EMA Crossover",
        description="Old container",
        market_type=MarketType.EQUITY,
        instrument="Any",
        timeframe=Timeframe.M15,
        status=StrategyStatus.TESTING,
        confidence_level=5,
        priority=Priority.MEDIUM,
        library_strategy_id=LIBRARY_STRATEGY_ID,
        deleted_at=datetime.now(UTC),
    )
    repo.add(deleted)
    db_session.commit()

    assert repo.get_by_name("EMA Crossover") is None
    assert repo.is_name_taken("EMA Crossover") is True

    service = ExecutionService(db_session, get_data_paths(settings))
    container = service._ensure_library_container(service.library.get(LIBRARY_STRATEGY_ID))

    assert container.name == "EMA Crossover (Library 2)"
    assert container.library_strategy_id == LIBRARY_STRATEGY_ID
    assert container.deleted_at is None
