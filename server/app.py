"""FastAPI application factory and lifespan management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import DEFAULT_DEV_TOKEN, get_api_token, get_cors_origins
from server.database import init_db
from server.middleware import ApiUsageMiddleware
from server.routers import (
    execute_agent,
    health,
    jobs,
    models,
    presets,
    projects,
    settings,
    stats,
    webhook,
    ws,
)
from server.worker import start_worker, stop_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    if get_api_token() == DEFAULT_DEV_TOKEN:
        logger.warning(
            "Using dev-only API token — set ORCHESTRATOR_API_TOKEN or WEBHOOK_TOKEN in production"
        )

    init_db()
    await start_worker()
    logger.info("HyperOrchestrator platform API started")
    yield
    await stop_worker()
    logger.info("HyperOrchestrator platform API stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="HyperOrchestrator Platform API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ApiUsageMiddleware)

    app.include_router(health.router)
    app.include_router(settings.router)
    app.include_router(stats.router)
    app.include_router(presets.router)
    app.include_router(models.router)
    app.include_router(projects.router)
    app.include_router(jobs.router)
    app.include_router(webhook.router)
    app.include_router(execute_agent.router)
    app.include_router(ws.router)

    return app


app = create_app()
