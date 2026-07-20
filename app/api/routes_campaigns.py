"""Campaign generation endpoints (protected)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from app.api.schemas import CampaignAccepted, CreateCampaignRequest
from app.deps import enforce_rate_limit, get_container
from app.errors import NotFoundError, ValidationAppError
from app.graph.state import CampaignState
from app.metrics import CAMPAIGN_GENERATIONS
from app.security.auth import (
    SCOPE_CAMPAIGNS_READ,
    SCOPE_CAMPAIGNS_WRITE,
    require_scope,
)
from app.security.jwt import Principal

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
    state = CampaignState(request_id=request_id, brief=brief, model_label=container.model_label)
    plan = await container.pipeline.run(state)
    container.store.save(plan)
    CAMPAIGN_GENERATIONS.inc()
    return CampaignAccepted(id=plan.id, plan=plan)


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
