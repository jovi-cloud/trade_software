"""Strategy code request/response DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

CODE_MAX_LENGTH = 200_000


class StrategyCodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_id: str
    code: str
    compiled_successfully: bool
    compile_error: str | None
    created_at: datetime
    updated_at: datetime


class StrategyCodeUpdate(BaseModel):
    code: str = Field(max_length=CODE_MAX_LENGTH)


class StrategyCodeValidateRequest(BaseModel):
    code: str = Field(max_length=CODE_MAX_LENGTH)


class SyntaxErrorDetail(BaseModel):
    line: int | None
    column: int | None
    message: str


class StrategyValidationResult(BaseModel):
    valid: bool
    error: SyntaxErrorDetail | None = None
