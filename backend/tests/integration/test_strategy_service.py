"""StrategyService against a real temp SQLite file (ARCHITECTURE.md 9)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.enums import MarketType, Priority, StrategyStatus, Timeframe
from app.models.strategy import Strategy
from app.schemas.strategy import StrategyCreate, StrategyUpdate
from app.services.strategy_service import StrategyService


def _create(service: StrategyService, **overrides: object) -> Strategy:
    defaults: dict[str, object] = {
        "name": "Opening Range Breakout",
        "description": "Buys the breakout of the first 15-minute range.",
        "hypothesis": "Early volatility expansion tends to continue intraday.",
        "market_type": MarketType.EQUITY,
        "instrument": "NIFTY",
        "timeframe": Timeframe.M15,
        "status": StrategyStatus.DRAFT,
        "confidence_level": 5,
        "priority": Priority.MEDIUM,
        "tags": "intraday, breakout",
    }
    defaults.update(overrides)
    return service.create(StrategyCreate(**defaults))


def test_create_normalizes_tags_and_trims_fields(db_session: Session) -> None:
    service = StrategyService(db_session)

    strategy = _create(service, name="  ORB  ", tags=" intraday , breakout ,intraday ")

    assert strategy.name == "ORB"
    assert strategy.tags == "intraday, breakout"


def test_create_rejects_duplicate_name(db_session: Session) -> None:
    service = StrategyService(db_session)
    _create(service)

    with pytest.raises(ConflictError):
        _create(service)


def test_get_missing_strategy_raises_not_found(db_session: Session) -> None:
    service = StrategyService(db_session)

    with pytest.raises(NotFoundError):
        service.get("does-not-exist")


def test_update_can_clear_optional_fields_but_not_required_ones(db_session: Session) -> None:
    service = StrategyService(db_session)
    strategy = _create(service)

    updated = service.update(strategy.id, StrategyUpdate(hypothesis=None, tags=None))
    assert updated.hypothesis is None
    assert updated.tags is None

    with pytest.raises(ValidationError):
        service.update(strategy.id, StrategyUpdate(name=None))


def test_soft_deleted_strategy_is_excluded_from_get_and_list(db_session: Session) -> None:
    service = StrategyService(db_session)
    strategy = _create(service)

    service.delete(strategy.id)

    with pytest.raises(NotFoundError):
        service.get(strategy.id)

    items, total = service.list(
        q=None, status=None, sort="updated_at", order="desc", limit=20, offset=0
    )
    assert items == []
    assert total == 0


def test_list_filters_by_status_and_search(db_session: Session) -> None:
    service = StrategyService(db_session)
    _create(service, name="ORB Nifty", status=StrategyStatus.DRAFT)
    _create(
        service,
        name="Mean Reversion BTC",
        status=StrategyStatus.TESTING,
        instrument="BTCUSD",
        market_type=MarketType.CRYPTO,
    )

    items, total = service.list(
        q=None, status=StrategyStatus.TESTING, sort="updated_at", order="desc", limit=20, offset=0
    )
    assert total == 1
    assert items[0].name == "Mean Reversion BTC"

    items, total = service.list(
        q="orb", status=None, sort="updated_at", order="desc", limit=20, offset=0
    )
    assert total == 1
    assert items[0].name == "ORB Nifty"


def test_stats_counts_by_status_and_lists_recent_research(db_session: Session) -> None:
    service = StrategyService(db_session)
    _create(service, name="A", status=StrategyStatus.DRAFT)
    _create(service, name="B", status=StrategyStatus.TESTING, priority=Priority.HIGH)
    _create(service, name="C", status=StrategyStatus.VALIDATED)

    stats = service.stats()

    assert stats["total"] == 3
    assert stats["draft"] == 1
    assert stats["testing"] == 1
    assert stats["validated"] == 1
    assert len(stats["recent_research"]) == 3  # type: ignore[arg-type]
    assert [s.name for s in stats["high_priority"]] == ["B"]  # type: ignore[attr-defined]
    assert [s.name for s in stats["needs_review"]] == ["B"]  # type: ignore[attr-defined]


def test_update_rejects_confidence_level_out_of_range(db_session: Session) -> None:
    service = StrategyService(db_session)
    strategy = _create(service)

    with pytest.raises(ValueError):
        StrategyUpdate(confidence_level=0)

    updated = service.update(strategy.id, StrategyUpdate(confidence_level=9))
    assert updated.confidence_level == 9
