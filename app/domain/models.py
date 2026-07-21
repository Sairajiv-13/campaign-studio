"""Core domain models for campaign generation and scoring.

These are the typed objects that flow through the pipeline. A ``Brief`` (the
marketer's input) fans out into ``Variant``s per segment, each of which is scored
into a ``ScoredVariant``; the best per segment roll up into a ``CampaignPlan``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import Channel, Goal, Tone


class BrandVoice(BaseModel):
    tone: Tone = Tone.FRIENDLY
    guidelines: str = ""
    # Phrases the brand refuses to use (compliance / off-brand). A hard signal:
    # any variant containing one is penalized heavily on brand voice.
    banned_phrases: list[str] = Field(default_factory=list)


class Segment(BaseModel):
    """A named audience with descriptive traits used to personalize copy."""

    id: str
    name: str
    description: str = ""
    traits: list[str] = Field(default_factory=list)
    # Optional offer emphasis for this segment (e.g. "10% off", "free shipping").
    incentive: str = ""


class Brief(BaseModel):
    product_name: str
    product_description: str
    value_props: list[str] = Field(default_factory=list)
    brand_voice: BrandVoice = Field(default_factory=BrandVoice)
    goal: Goal = Goal.RE_ENGAGEMENT
    channels: list[Channel] = Field(default_factory=lambda: [Channel.EMAIL])
    segments: list[Segment]
    variants_per_segment: int = 3


class Variant(BaseModel):
    """One generated piece of copy for one segment on one channel."""

    id: str
    segment_id: str
    channel: Channel
    angle: str = ""  # the messaging angle the generator chose
    subject: str = ""  # email only
    preview_text: str = ""  # email only
    body: str


class ScoreBreakdown(BaseModel):
    """Per-dimension quality scores in [0, 1] plus a weighted composite."""

    brand_voice: float = Field(ge=0.0, le=1.0)
    clarity: float = Field(ge=0.0, le=1.0)
    cta_strength: float = Field(ge=0.0, le=1.0)
    personalization: float = Field(ge=0.0, le=1.0)
    deliverability: float = Field(ge=0.0, le=1.0)
    composite: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class ScoredVariant(BaseModel):
    variant: Variant
    score: ScoreBreakdown


class SegmentPlan(BaseModel):
    segment_id: str
    segment_name: str
    scored_variants: list[ScoredVariant]  # sorted by composite, descending
    winner: ScoredVariant
    runner_up: ScoredVariant | None = None


class CampaignPlan(BaseModel):
    id: str
    goal: Goal
    channels: list[Channel]
    product_name: str
    segment_plans: list[SegmentPlan]
    model: str  # "sandbox" or the real model id, for provenance
    # Estimated generation cost at published provider rates (ADR-004). 0.0 in
    # sandbox mode. An estimate, not a billed amount.
    cost_usd: float = 0.0
