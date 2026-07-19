"""FastAPI application factory."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.config import get_settings
from app.deps import build_container
from app.errors import register_error_handlers
from app.logging import configure_logging, get_logger
from app.observability import CorrelationMiddleware, SecurityMiddleware

logger = get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.container = build_container(settings)
    logger.info("studio_started", extra={"model": app.state.container.model_label})
    try:
        yield
    finally:
        await app.state.container.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Lifecycle Campaign Studio",
        version=__version__,
        summary="Generate and score personalized marketing campaigns per audience segment.",
        lifespan=lifespan,
    )

    app.add_middleware(SecurityMiddleware, max_body_bytes=settings.max_request_bytes)
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
