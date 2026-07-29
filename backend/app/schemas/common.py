"""Shared response envelopes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable description")
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """The single error shape every endpoint returns on failure."""

    error: ErrorDetail


class Page[T](BaseModel):
    """Standard list envelope: ``{items, total, limit, offset}``."""

    items: list[T]
    total: int
    limit: int
    offset: int


class IdResponse(BaseModel):
    id: str
