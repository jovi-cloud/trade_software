"""Logging setup: stdlib logging with a console or JSON formatter.

Deliberately dependency-free. Structured context (run_id, job_id) is attached
with ``logger.info(msg, extra={"run_id": ...})`` and rendered by both formatters.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

from app.core.config import Settings

# LogRecord attributes that are not caller-supplied context.
_RESERVED: frozenset[str] = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | frozenset({"message", "asctime", "taskName"})


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    """Whatever the caller passed via ``extra=``."""
    return {k: v for k, v in record.__dict__.items() if k not in _RESERVED}


class ConsoleFormatter(logging.Formatter):
    """Human-readable single line, with extras appended as key=value."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s %(name)-28s %(message)s",
            datefmt="%H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = _extra_fields(record)
        if extras:
            base += "  " + " ".join(f"{k}={v}" for k, v in extras.items())
        return base


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for when logs are grepped rather than read."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **_extra_fields(record),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings, log_dir: Path | None = None) -> None:
    """Install handlers on the root logger. Safe to call once at startup."""
    formatter = JsonFormatter() if settings.log_format == "json" else ConsoleFormatter()

    root = logging.getLogger()
    root.setLevel(settings.log_level)
    for existing in list(root.handlers):
        root.removeHandler(existing)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    if settings.log_to_file and log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter())
        root.addHandler(file_handler)

    # Uvicorn installs its own handlers; route them through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.log_level == "DEBUG" else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
