"""StrategyCodeService against a real temp SQLite file (ARCHITECTURE.md 9)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.domain.enums import MarketType, Priority, StrategyStatus, Timeframe
from app.schemas.strategy import StrategyCreate
from app.services.strategy_code_service import DEFAULT_STRATEGY_TEMPLATE, StrategyCodeService
from app.services.strategy_service import StrategyService


def _create_strategy(session: Session) -> str:
    service = StrategyService(session)
    strategy = service.create(
        StrategyCreate(
            name="Opening Range Breakout",
            description="Buys the breakout of the first 15-minute range.",
            market_type=MarketType.EQUITY,
            instrument="NIFTY",
            timeframe=Timeframe.M15,
            status=StrategyStatus.DRAFT,
            confidence_level=5,
            priority=Priority.MEDIUM,
        )
    )
    return strategy.id


def test_get_or_create_seeds_default_template(db_session: Session) -> None:
    strategy_id = _create_strategy(db_session)
    service = StrategyCodeService(db_session)

    record = service.get_or_create(strategy_id)

    assert record.code == DEFAULT_STRATEGY_TEMPLATE
    assert record.compiled_successfully is True
    assert record.compile_error is None

    # Second call returns the same row rather than reseeding.
    again = service.get_or_create(strategy_id)
    assert again.id == record.id


def test_get_or_create_raises_not_found_for_missing_strategy(db_session: Session) -> None:
    service = StrategyCodeService(db_session)

    with pytest.raises(NotFoundError):
        service.get_or_create("does-not-exist")


def test_update_persists_code_and_syntax_result(db_session: Session) -> None:
    strategy_id = _create_strategy(db_session)
    service = StrategyCodeService(db_session)
    service.get_or_create(strategy_id)

    updated = service.update(
        strategy_id, "class Strategy:\n    def on_start(self):\n        x = 1\n"
    )

    assert updated.compiled_successfully is True
    assert updated.compile_error is None
    assert "x = 1" in updated.code


def test_update_records_syntax_error_without_raising(db_session: Session) -> None:
    strategy_id = _create_strategy(db_session)
    service = StrategyCodeService(db_session)

    updated = service.update(strategy_id, "def broken(:\n    pass")

    assert updated.compiled_successfully is False
    assert updated.compile_error is not None


def test_validate_does_not_persist(db_session: Session) -> None:
    strategy_id = _create_strategy(db_session)
    service = StrategyCodeService(db_session)

    result = service.validate(strategy_id, "def broken(:\n    pass")
    assert result.valid is False
    assert result.error is not None
    assert result.error.line == 1

    # Validating never creates a row.
    from app.repositories.strategy_code_repo import StrategyCodeRepository

    assert StrategyCodeRepository(db_session).get_by_strategy_id(strategy_id) is None


def test_validate_valid_code(db_session: Session) -> None:
    strategy_id = _create_strategy(db_session)
    service = StrategyCodeService(db_session)

    result = service.validate(strategy_id, DEFAULT_STRATEGY_TEMPLATE)

    assert result.valid is True
    assert result.error is None
