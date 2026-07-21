"""Campaign generation endpoints (protected)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from app.api.schemas import CampaignAccepted, CreateCampaignRequest
from app.cost import current_total_usd, open_ledger
from app.deps import enforce_rate_limit, get_container
from app.errors import NotFoundError, ValidationAppError
from app.graph.state import CampaignState
from app.logging import get_logger
from app.metrics import (
    BUDGET_TRIPPED,
    CAMPAIGN_COST,
    CAMPAIGN_GENERATIONS,
)
from app.security.auth import (
    SCOPE_CAMPAIGNS_READ,
    SCOPE_CAMPAIGNS_WRITE,
    require_scope,
)
from app.security.jwt import Principal

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["campaigns"])


@router.post("/campaigns", status_code=201, response_model=CampaignAccepted)
async def create_campaign(
    payload: CreateCampaignRequest,
    request: Request,
    _principal: Principal = Depends(require_scope(SCOPE_CAMPAIGNS_WRITE)),
    __: None = Depends(enforce_rate_limit),
) -> CampaignAccepted:
    container = get_container(request)
    settings = container.settings

    # Enforce the deployment's configured caps (schema enforces absolute maxima).
    brief = payload.brief
    if len(brief.segments) > settings.max_segments:
        raise ValidationAppError(f"at most {settings.max_segments} segments are allowed")
    brief.variants_per_segment = min(brief.variants_per_segment, settings.max_variants_per_segment)

    request_id = uuid.uuid4().hex

    # Cost circuit breaker (ADR-004): once today's spend hits the cap, generate on
    # the free sandbox model instead of billing more. Checked once per request.
    degraded = container.budget.should_degrade()
    if degraded:
        logger.warning("budget_cap_tripped", extra={"spent_usd": container.budget.spent_today})
        BUDGET_TRIPPED.inc()
        pipeline = container.degraded_pipeline
        model_label = "sandbox"
    else:
        if container.budget.is_warning():
            logger.warning("budget_warn", extra={"spent_usd": container.budget.spent_today})
        pipeline = container.pipeline
        model_label = container.model_label

    state = CampaignState(request_id=request_id, brief=brief, model_label=model_label)
    with open_ledger():
        plan = await pipeline.run(state)
        plan.cost_usd = current_total_usd()

    container.budget.add(plan.cost_usd)
    container.store.save(plan)
    CAMPAIGN_GENERATIONS.inc()
    CAMPAIGN_COST.observe(plan.cost_usd)
    return CampaignAccepted(id=plan.id, plan=plan)


@router.get("/usage")
async def get_usage(
    request: Request,
    _principal: Principal = Depends(require_scope(SCOPE_CAMPAIGNS_READ)),
) -> dict[str, object]:
    """Today's estimated LLM spend and the budget cap state (ADR-004).

    Spend is an estimate at published rates and is process-local (resets on
    restart) — see the ADR for why that's an accepted limitation here.
    """

    container = get_container(request)
    budget = container.budget
    return {
        "spent_today_usd": budget.spent_today,
        "warn_usd": container.settings.daily_budget_warn_usd,
        "cap_usd": container.settings.daily_budget_cap_usd,
        "degraded": budget.should_degrade(),
        "note": "estimate at published rates; process-local",
    }


@router.get("/campaigns/{campaign_id}", response_model=CampaignAccepted)
async def get_campaign(
    campaign_id: str,
    request: Request,
    _principal: Principal = Depends(require_scope(SCOPE_CAMPAIGNS_READ)),
) -> CampaignAccepted:
    plan = get_container(request).store.get(campaign_id)
    if plan is None:
        raise NotFoundError(f"Campaign '{campaign_id}' not found")
    return CampaignAccepted(id=plan.id, plan=plan)
