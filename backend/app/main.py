"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.paths import get_data_paths
from app.core.runtime import frontend_dist_dir, is_frozen
from app.db.session import dispose_engine, get_session_factory
from app.jobs.runner import ThreadPoolJobRunner

logger = logging.getLogger(__name__)


def _mount_frontend(app: FastAPI, dist_dir: Path) -> None:
    """Serve the Vite production build with SPA fallback (``html=True``)."""
    if not dist_dir.is_dir():
        logger.warning("Frontend dist not found at %s; API-only mode", dist_dir)
        return

    index_path = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"
    if not index_path.is_file():
        logger.error("Frontend index.html missing at %s", index_path)
        return
    if not assets_dir.is_dir():
        logger.error("Frontend assets directory missing at %s", assets_dir)
        return

    logger.info(
        "Serving frontend from %s (%d asset files)",
        dist_dir,
        len(list(assets_dir.iterdir())),
    )
    # Explicit /assets mount first so JS/CSS bundles are never swallowed by the SPA fallback.
    app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend_assets")
    # Registered after API routes so /api/* is never swallowed by the static mount.
    app.mount(
        "/",
        StaticFiles(directory=dist_dir, html=True),
        name="frontend",
    )


def _prepare_frozen_environment(settings: Settings) -> None:
    """First-run seed copy and schema migrations for the packaged desktop build."""
    from app.core.migrations import run_migrations
    from app.core.seed_data import ensure_seed_data

    ensure_seed_data(settings.data_dir)
    run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    app.state.job_runner = ThreadPoolJobRunner(settings, session_factory=get_session_factory())
    logger.info(
        "Starting %s", settings.app_name, extra={"env": settings.env, "port": settings.port}
    )
    yield
    app.state.job_runner.shutdown()
    dispose_engine()
    logger.info("Shutdown complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    if is_frozen():
        _prepare_frozen_environment(settings)

    paths = get_data_paths(settings)
    paths.ensure()
    configure_logging(settings, log_dir=paths.logs)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Local, single-user trading strategy research platform.",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    if is_frozen() or frontend_dist_dir().is_dir():
        _mount_frontend(app, frontend_dist_dir())

    return app
