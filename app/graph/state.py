"""The state threaded through the campaign pipeline.

One typed Pydantic object every node reads from and contributes to. Nodes return
only the fields they changed; LangGraph merges the delta. Keeping it in one model
makes the state validated and serializable (for API responses and debugging).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models import Brief, CampaignPlan, ScoredVariant, Variant


class CampaignState(BaseModel):
    request_id: str
    brief: Brief
    model_label: str = "sandbox"

    variants: list[Variant] = Field(default_factory=list)
    scored: list[ScoredVariant] = Field(default_factory=list)
    plan: CampaignPlan | None = None
    # Count of generation slots that fell back to a template (ADR-005).
    fallback_count: int = 0
