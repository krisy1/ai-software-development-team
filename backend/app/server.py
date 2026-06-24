from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.registry import init_registry
from app.api.router import router
from app.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger, setup_logging
from app.core.middleware import register_middleware
from app.db.base import Base
from app.db.session import engine
from app.models.db import (  # noqa: F401 — register all models
    ArtifactModel,
    ExecutionModel,
    ProjectModel,
)
from app.services.llm_service import llm_service
from app.services.vector_store import vector_store

Instrumentator: type | None = None
HAS_PROMETHEUS = False
try:
    from prometheus_fastapi_instrumentator import Instrumentator as _Instrumentator

    Instrumentator = _Instrumentator
    HAS_PROMETHEUS = True
except ImportError:
    pass

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize and shutdown services."""
    setup_logging()
    logger.info(
        "application_starting",
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

    # Initialize database
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_verified")

    # Initialize external services
    await llm_service.initialize()
    await vector_store.initialize()

    # Initialize agent registry
    if llm_service.is_available:
        reg = init_registry(llm_service)
        logger.info("agent_registry_initialized", agents=reg.available_agents)
    else:
        logger.warning("agent_registry not initialized: LLM service unavailable")

    # Verify storage layer
    from app.services.storage_service import storage_service

    storage_service._ensure_dirs()
    logger.info("storage_layer_ready")

    # Pre-compile the pipeline
    from app.graph.pipeline import get_pipeline

    get_pipeline()
    logger.info("langgraph_pipeline_compiled")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Multi-agent AI system that simulates a complete software development team",
        lifespan=lifespan,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware
    register_middleware(app)

    # Prometheus metrics
    if HAS_PROMETHEUS and Instrumentator is not None:
        Instrumentator().instrument(app).expose(app)

    # Exception handler
    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "status_code": exc.status_code,
                "errors": [exc.details] if exc.details else None,
            },
        )

    # Routes
    app.include_router(router)

    # Health check
    @app.get("/health")
    async def health_check() -> dict:
        return {
            "status": "healthy",
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    return app


app = create_app()
