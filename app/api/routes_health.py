"""Health and metrics endpoints (public).

``/metrics`` is left unauthenticated so a Prometheus scraper can reach it; in a
real deployment it sits on an internal network or is gated at the ingress.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app import __version__, metrics
from app.deps import get_container

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    container = get_container(request)
    return {
        "status": "ok",
        "version": __version__,
        "model": container.model_label,
        "campaigns": container.store.count(),
    }


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    return Response(content=metrics.render(), media_type=metrics.CONTENT_TYPE)
