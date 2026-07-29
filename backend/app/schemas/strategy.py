"""Strategy request/response DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import MarketType, Priority, StrategyStatus, Timeframe

TAGS_MAX_LENGTH = 500
LONG_TEXT_MAX_LENGTH = 8000


def _require_non_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class StrategyCreate(BaseModel):
    # Research
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    hypothesis: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    market_type: MarketType = MarketType.EQUITY
    instrument: str = Field(min_length=1, max_length=100)
    timeframe: Timeframe

    # Trading rules
    entry_rules: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    exit_rules: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)

    # Risk management
    stop_loss_method: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    target_method: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    position_sizing: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)

    # Research notes
    assumptions: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    known_weaknesses: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    ideas_for_improvement: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)

    # Status
    status: StrategyStatus = StrategyStatus.DRAFT
    confidence_level: int = Field(default=5, ge=1, le=10)
    priority: Priority = Priority.MEDIUM

    tags: str | None = Field(default=None, max_length=TAGS_MAX_LENGTH)

    @field_validator("name", "description", "instrument")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        return _require_non_blank(value)


class StrategyUpdate(BaseModel):
    """All fields optional: only keys present in the payload are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    hypothesis: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    market_type: MarketType | None = None
    instrument: str | None = Field(default=None, min_length=1, max_length=100)
    timeframe: Timeframe | None = None

    entry_rules: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    exit_rules: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)

    stop_loss_method: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    target_method: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    position_sizing: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)

    assumptions: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    known_weaknesses: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)
    ideas_for_improvement: str | None = Field(default=None, max_length=LONG_TEXT_MAX_LENGTH)

    status: StrategyStatus | None = None
    confidence_level: int | None = Field(default=None, ge=1, le=10)
    priority: Priority | None = None

    tags: str | None = Field(default=None, max_length=TAGS_MAX_LENGTH)


class StrategyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    hypothesis: str | None
    market_type: MarketType
    instrument: str
    timeframe: Timeframe

    entry_rules: str | None
    exit_rules: str | None

    stop_loss_method: str | None
    target_method: str | None
    position_sizing: str | None

    assumptions: str | None
    known_weaknesses: str | None
    ideas_for_improvement: str | None

    status: StrategyStatus
    confidence_level: int
    priority: Priority

    tags: str | None
    created_at: datetime
    updated_at: datetime


class StrategyStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int
    draft: int
    testing: int
    validated: int
    archived: int
    rejected: int
    high_priority: list[StrategyRead]
    recent_research: list[StrategyRead]
    needs_review: list[StrategyRead]
