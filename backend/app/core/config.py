"""Application settings, loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.runtime import REPO_ROOT, default_data_dir, is_frozen


def _settings_config() -> SettingsConfigDict:
    if is_frozen():
        return SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")
    return SettingsConfigDict(
        env_file=REPO_ROOT / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings(BaseSettings):
    """Runtime configuration. Every value has a working default: the app must
    start with no .env file present."""

    model_config = _settings_config()

    # --- Application ---
    app_name: str = "Trading Strategy Research Platform"
    env: Literal["dev", "test", "prod"] = Field(
        default_factory=lambda: "prod" if is_frozen() else "dev"
    )
    debug: bool = Field(default_factory=lambda: not is_frozen())
    api_v1_prefix: str = "/api/v1"

    # --- Server. Loopback only: this is a single-user local application. ---
    host: str = "127.0.0.1"
    port: int = 8001

    # --- Storage. All user state lives under this one directory. ---
    data_dir: Path = Field(default_factory=default_data_dir)

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
        default_factory=lambda: (
            []
            if is_frozen()
            else ["http://localhost:5174", "http://127.0.0.1:5174"]
        )
    )

    @field_validator("data_dir")
    @classmethod
    def _absolute_data_dir(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        if is_frozen():
            return default_data_dir().parent / value
        return (REPO_ROOT / value).resolve()

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
