"""API request/response models.

The request is validated against the domain model plus a few boundary limits
(segment/variant caps, control-character stripping, size). Responses reuse the
domain ``CampaignPlan`` directly since it is already a clean Pydantic model.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.models import Brief, CampaignPlan

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class TokenRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CreateCampaignRequest(BaseModel):
    """A campaign brief plus boundary validation."""

    brief: Brief

    @field_validator("brief")
    @classmethod
    def _validate_brief(cls, brief: Brief) -> Brief:
        if not brief.product_name.strip():
            raise ValueError("product_name is required")
        if not brief.segments:
            raise ValueError("at least one segment is required")
        # Sanitize free text that feeds prompts.
        brief.product_name = _clean(brief.product_name)
        brief.product_description = _clean(brief.product_description)
        return brief

    @model_validator(mode="after")
    def _enforce_limits(self) -> CreateCampaignRequest:
        # Hard caps are re-checked in the route against Settings; these are the
        # absolute maxima that keep a single request bounded regardless of config.
        if len(self.brief.segments) > 20:
            raise ValueError("too many segments (max 20)")
        if not 1 <= self.brief.variants_per_segment <= 10:
            raise ValueError("variants_per_segment must be between 1 and 10")
        return self


class CampaignAccepted(BaseModel):
    id: str
    plan: CampaignPlan


def _clean(value: str) -> str:
    return _CONTROL_CHARS.sub("", value).strip()
