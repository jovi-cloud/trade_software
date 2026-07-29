"""Application exception hierarchy.

Services and the engine raise these. Only ``app/api/errors.py`` translates them
into HTTP responses - nothing below the router layer knows about status codes.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base for every error this application raises deliberately.

    ``code`` is the stable machine-readable string the frontend switches on;
    ``message`` is shown to the user.
    """

    code: str = "APP_ERROR"
    http_status: int = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = 404


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    http_status = 422


class ConflictError(AppError):
    code = "CONFLICT"
    http_status = 409


class DomainError(AppError):
    """A rule of the trading/research domain was violated."""

    code = "DOMAIN_ERROR"
    http_status = 400
