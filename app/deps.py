"""Composition root.

The one place that reads configuration and constructs concrete implementations
(real vs sandbox LLM, the compiled pipeline, the store, the limiter). Everything
else depends on abstractions. The assembled Container is attached to app.state.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol

from fastapi import Request

from app.config import LlmMode, Settings
from app.cost import BudgetTracker
from app.graph.build import Pipeline
from app.graph.context import NodeContext
from app.llm.base import LlmPort
from app.llm.openai_compatible import OpenAICompatibleLlm
from app.llm.sandbox import SandboxLlm
from app.logging import get_logger
from app.security.auth import hash_password
from app.security.rate_limit import RateLimiter
from app.store import CampaignStore

logger = get_logger(__name__)


class _Closable(Protocol):
    async def aclose(self) -> None: ...


@dataclass
class Container:
    settings: Settings
    llm: LlmPort
    pipeline: Pipeline
    # Sandbox-only pipeline used when the daily budget cap trips (ADR-004).
    degraded_pipeline: Pipeline
    budget: BudgetTracker
    store: CampaignStore
    rate_limiter: RateLimiter
    model_label: str
    service_account_id: str
    service_account_password_hash: str
    _closables: list[_Closable] = field(default_factory=list)

    async def aclose(self) -> None:
        for closable in self._closables:
            try:
                await closable.aclose()
            except Exception as exc:  # noqa: BLE001 - best-effort shutdown
                logger.warning("closable_shutdown_failed", extra={"detail": str(exc)})


def build_llm(settings: Settings, closables: list[_Closable]) -> tuple[LlmPort, str]:
    if settings.llm_mode is LlmMode.REAL:
        adapter = OpenAICompatibleLlm(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
        closables.append(adapter)
        return adapter, settings.llm_model
    return SandboxLlm(), "sandbox"


def build_container(settings: Settings) -> Container:
    closables: list[_Closable] = []
    llm, model_label = build_llm(settings, closables)
    pipeline = Pipeline(NodeContext(llm=llm, model_label=model_label))
    # Always-free fallback pipeline for when the budget cap trips. Built once.
    degraded_pipeline = Pipeline(NodeContext(llm=SandboxLlm(), model_label="sandbox"))
    return Container(
        settings=settings,
        llm=llm,
        pipeline=pipeline,
        degraded_pipeline=degraded_pipeline,
        budget=BudgetTracker(
            warn_usd=settings.daily_budget_warn_usd,
            cap_usd=settings.daily_budget_cap_usd,
        ),
        store=CampaignStore(),
        rate_limiter=RateLimiter(
            limit=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        ),
        model_label=model_label,
        service_account_id=settings.service_account_id,
        service_account_password_hash=hash_password(settings.service_account_password),
        _closables=closables,
    )


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


def enforce_rate_limit(request: Request) -> None:
    container = get_container(request)
    container.rate_limiter.check(_rate_limit_identity(request))


def _rate_limit_identity(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        digest = hashlib.sha256(auth.split(" ", 1)[1].encode("utf-8")).hexdigest()[:32]
        return f"token:{digest}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"
