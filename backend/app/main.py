"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.paths import get_data_paths
from app.db.session import dispose_engine, get_session_factory
from app.jobs.runner import ThreadPoolJobRunner

logger = logging.getLogger(__name__)


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
    return app


app = create_app()
