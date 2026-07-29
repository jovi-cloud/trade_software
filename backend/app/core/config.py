"""Application settings, loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> <repo root>
REPO_ROOT: Path = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration. Every value has a working default: the app must
    start with no .env file present."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Trading Strategy Research Platform"
    env: Literal["dev", "test", "prod"] = "dev"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # --- Server. Loopback only: this is a single-user local application. ---
    host: str = "127.0.0.1"
    port: int = 8000

    # --- Storage. All user state lives under this one directory. ---
    data_dir: Path = REPO_ROOT / "data"

    # --- Database. Empty means "derive from data_dir" (see database_url). ---
    database_url: str = ""

    # --- Logging ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["console", "json"] = "console"
    log_to_file: bool = True

    # --- Jobs. In-process thread pool; see ARCHITECTURE.md 2.4. ---
    job_max_workers: int = 2

    # --- CORS: the Vite dev server. Not needed once the frontend is built
    # and served by FastAPI, but required during development. ---
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    @field_validator("data_dir")
    @classmethod
    def _absolute_data_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()

    @property
    def sqlalchemy_url(self) -> str:
        """SQLite URL. Defaults to <data_dir>/app.db unless DATABASE_URL is set."""
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.data_dir / 'app.db'}"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor. Import this, never a module-level Settings instance."""
    return Settings()
