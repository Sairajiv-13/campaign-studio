"""Health endpoint (public)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app import __version__
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
