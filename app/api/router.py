"""Aggregate router mounting every endpoint group."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import routes_auth, routes_campaigns, routes_health, routes_ui

api_router = APIRouter()
api_router.include_router(routes_ui.router)
api_router.include_router(routes_health.router)
api_router.include_router(routes_auth.router)
api_router.include_router(routes_campaigns.router)
