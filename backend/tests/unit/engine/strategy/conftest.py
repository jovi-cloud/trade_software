"""Fixtures for strategy framework tests.

The minimal-but-valid metadata factory here is what lets a test declare only the
one field it is exercising: without it every validation test would carry forty
lines of unrelated metadata and the assertion would be invisible.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.domain.enums import MarketType, RiskLevel, StrategyCategory, Timeframe
from app.engine.bars import Bar
from app.engine.strategy.metadata import (
    ChangelogEntry,
    StrategyDocumentation,
    StrategyExample,
    StrategyMetadata,
)

DAY_MS = 86_400_000
EPOCH_MS = 1_704_067_200_000


def make_metadata(**overrides: object) -> StrategyMetadata:
    """Metadata that passes validation with zero findings, before overrides."""
    base: dict[str, object] = {
        "id": "test_strategy",
        "name": "Test Strategy",
        "description": "A strategy used by the framework tests.",
        "version": "1.0.0",
        "author": "Tests",
        "category": StrategyCategory.TREND_FOLLOWING,
        "markets": (MarketType.EQUITY,),
        "timeframes": (Timeframe.D1,),
        "tags": ("test",),
        "risk_level": RiskLevel.MEDIUM,
        "supports_long": True,
        "supports_short": True,
        "supports_intraday": False,
        "supports_swing": True,
        "supports_position_trading": False,
        "documentation": StrategyDocumentation(
            overview="What this strategy does.",
            indicators=("An indicator",),
            entry_rules=("Enter sometimes",),
            exit_rules=("Exit sometimes",),
            known_limitations=("It is a test",),
        ),
        "examples": (
            StrategyExample(
                title="Default",
                description="Defaults on daily bars.",
                instrument="TEST",
                timeframe=Timeframe.D1,
            ),
        ),
        "changelog": (
            ChangelogEntry(version="1.0.0", date="2026-07-30", changes=("First release",)),
        ),
    }
    base.update(overrides)
    return StrategyMetadata(**base)  # type: ignore[arg-type]


def bars_from_closes(values: Sequence[float], *, step_ms: int = DAY_MS) -> list[Bar]:
    return [
        Bar(
            ts=EPOCH_MS + index * step_ms,
            open=value,
            high=value,
            low=value,
            close=value,
            volume=1_000.0,
        )
        for index, value in enumerate(values)
    ]


def bars_from_ohlc(
    rows: Sequence[tuple[float, float, float, float]], *, step_ms: int = DAY_MS
) -> list[Bar]:
    return [
        Bar(
            ts=EPOCH_MS + index * step_ms,
            open=row[0],
            high=row[1],
            low=row[2],
            close=row[3],
            volume=1_000.0,
        )
        for index, row in enumerate(rows)
    ]


@pytest.fixture
def metadata() -> StrategyMetadata:
    return make_metadata()
