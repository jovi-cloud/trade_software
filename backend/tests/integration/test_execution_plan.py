"""``ExecutionService.plan`` - the decision the run workflow rests on.

Tested at the service level rather than only through HTTP because the router is
deliberately a pass-through: the choice of research container, the explain level
and the parameter resolution all live here.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.core.paths import get_data_paths
from app.domain.enums import Timeframe
from app.domain.explain import ExplainLevel
from app.models.strategy import Strategy
from app.services.execution_service import ExecutionService
from app.services.import_service import ImportService

VALID_CSV = (
    b"timestamp,open,high,low,close,volume\n"
    b"2024-01-01 09:15:00,100,101,99,100.5,1000\n"
    b"2024-01-01 09:16:00,100.5,102,100,101.5,1200\n"
)


def _service(session: Session, settings: Settings) -> ExecutionService:
    return ExecutionService(session, get_data_paths(settings))


def _dataset_id(session: Session, settings: Settings) -> str:
    dataset = ImportService(session, get_data_paths(settings)).import_csv(
        name="NIFTY 1m", symbol="NIFTY", exchange="NSE", timeframe=Timeframe.M1, content=VALID_CSV
    )
    return dataset.id


def test_plan_provisions_a_container_for_a_library_strategy(
    db_session: Session, settings: Settings
) -> None:
    service = _service(db_session, settings)

    plan = service.plan(
        dataset_id=_dataset_id(db_session, settings),
        library_strategy_id="rsi_mean_reversion",
        initial_capital=100_000,
        commission=0,
        slippage=0,
    )

    container = service.strategy_repo.get(plan.strategy_id)
    assert container is not None
    assert container.library_strategy_id == "rsi_mean_reversion"
    assert container.instrument == "Any"
    assert plan.strategy.library_strategy_id == "rsi_mean_reversion"
    assert plan.strategy.library_strategy_version == "1.0.0"


def test_plan_fills_unsupplied_parameters_from_the_declaration(
    db_session: Session, settings: Settings
) -> None:
    service = _service(db_session, settings)

    plan = service.plan(
        dataset_id=_dataset_id(db_session, settings),
        library_strategy_id="rsi_mean_reversion",
        strategy_params={"rsi_period": 7},
        initial_capital=100_000,
        commission=0,
        slippage=0,
    )

    defaults = service.library.default_params("rsi_mean_reversion")
    assert plan.strategy.params["rsi_period"] == 7
    assert set(plan.strategy.params) == set(defaults)


def test_plan_defaults_a_library_run_to_full_explainability(
    db_session: Session, settings: Settings
) -> None:
    plan = _service(db_session, settings).plan(
        dataset_id=_dataset_id(db_session, settings),
        library_strategy_id="rsi_mean_reversion",
        initial_capital=100_000,
        commission=0,
        slippage=0,
    )

    assert plan.config.explain_level is ExplainLevel.FULL


def test_a_large_dataset_is_not_defaulted_to_full_explainability(
    db_session: Session, settings: Settings
) -> None:
    """FULL records per *bar*, so defaulting to it scales with the dataset.

    Left unguarded, a 194k-bar intraday dataset produced a 460 MB decision log
    the save path could not serialise without exhausting memory - and one the
    engine's event budget would have truncated anyway.
    """
    service = _service(db_session, settings)

    assert (
        service.default_explain_level("rsi_mean_reversion", bar_count=194_553)
        is ExplainLevel.TRADES_ONLY
    )
    assert service.default_explain_level("rsi_mean_reversion", bar_count=500) is ExplainLevel.FULL


def test_a_large_dataset_may_still_be_run_at_full_on_request(
    db_session: Session, settings: Settings
) -> None:
    """The size guard picks a default; it must not override an explicit choice."""
    plan = _service(db_session, settings).plan(
        dataset_id=_dataset_id(db_session, settings),
        library_strategy_id="rsi_mean_reversion",
        explain_level=ExplainLevel.FULL,
        initial_capital=100_000,
        commission=0,
        slippage=0,
    )

    assert plan.config.explain_level is ExplainLevel.FULL


def test_plan_honours_an_explicit_explain_level(db_session: Session, settings: Settings) -> None:
    plan = _service(db_session, settings).plan(
        dataset_id=_dataset_id(db_session, settings),
        library_strategy_id="rsi_mean_reversion",
        explain_level=ExplainLevel.NONE,
        initial_capital=100_000,
        commission=0,
        slippage=0,
    )

    assert plan.config.explain_level is ExplainLevel.NONE


def test_plan_records_a_library_run_against_a_named_container(
    db_session: Session, settings: Settings
) -> None:
    """An explicit strategy_id wins: a library strategy can be run inside an
    existing research record without a second container appearing."""
    service = _service(db_session, settings)
    mine = Strategy(
        name="My Mean Reversion Research",
        description="Trying the built-in RSI strategy inside my own notes.",
        market_type="equity",
        instrument="NIFTY",
        timeframe="1m",
    )
    service.strategy_repo.add(mine)
    db_session.commit()

    plan = service.plan(
        dataset_id=_dataset_id(db_session, settings),
        strategy_id=mine.id,
        library_strategy_id="rsi_mean_reversion",
        initial_capital=100_000,
        commission=0,
        slippage=0,
    )

    assert plan.strategy_id == mine.id
    assert service.strategy_repo.get_by_library_strategy_id("rsi_mean_reversion") is None


def test_plan_needs_a_strategy_of_some_kind(db_session: Session, settings: Settings) -> None:
    with pytest.raises(ValidationError, match="Choose a strategy"):
        _service(db_session, settings).plan(
            dataset_id=_dataset_id(db_session, settings),
            initial_capital=100_000,
            commission=0,
            slippage=0,
        )
