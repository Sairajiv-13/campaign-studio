"""Serve the demo UI (public)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"])

_INDEX = Path(__file__).resolve().parent.parent / "web" / "index.html"


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> HTMLResponse:
    return HTMLResponse(_INDEX.read_text(encoding="utf-8"))
