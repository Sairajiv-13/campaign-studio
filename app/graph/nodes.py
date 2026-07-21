"""Pipeline nodes: generate, score, assemble.

Each node is an ``async (state, ctx) -> dict`` function returning only the fields
it changed. Nodes reach the model only through ``ctx.llm``. Generation degrades
gracefully: malformed model output falls back to a templated variant so a single
bad completion never sinks the whole campaign.
"""

from __future__ import annotations

import json
from typing import Any

from app.domain.enums import Channel
from app.domain.models import (
    Brief,
    CampaignPlan,
    ScoredVariant,
    Segment,
    SegmentPlan,
    Variant,
)
from app.graph.context import NodeContext
from app.graph.state import CampaignState
from app.llm.base import LlmAdapterError
from app.logging import get_logger
from app.metrics import GENERATION_FALLBACKS
from app.scoring.scorer import score_variant

logger = get_logger(__name__)


async def generate_node(state: CampaignState, ctx: NodeContext) -> dict[str, Any]:
    brief = state.brief
    variants: list[Variant] = []
    fallback_count = 0
    for segment in brief.segments:
        for channel in brief.channels:
            system, user = _generate_prompt(brief, segment, channel)
            try:
                raw = await ctx.llm.complete(
                    system=system, user=user, json_mode=True, temperature=0.7
                )
                items = _parse_variants(raw)
            except (LlmAdapterError, ValueError) as exc:
                logger.warning(
                    "generation_failed", extra={"segment": segment.id, "detail": str(exc)}
                )
                items = []

            if not items:
                # A single bad completion degrades this one slot to a template
                # rather than sinking the whole campaign (ADR-005). We count it so
                # the plan can honestly report reduced quality.
                items = [_fallback_variant(brief, segment, channel)]
                fallback_count += 1
                GENERATION_FALLBACKS.inc()

            for index, item in enumerate(items[: brief.variants_per_segment]):
                variants.append(_to_variant(segment, channel, index, item))
    return {"variants": variants, "fallback_count": fallback_count}


async def score_node(state: CampaignState, ctx: NodeContext) -> dict[str, Any]:
    segments = {segment.id: segment for segment in state.brief.segments}
    scored: list[ScoredVariant] = []
    for variant in state.variants:
        segment = segments.get(variant.segment_id)
        traits = segment.traits if segment else []
        breakdown = await score_variant(ctx.llm, variant, state.brief.brand_voice, traits)
        scored.append(ScoredVariant(variant=variant, score=breakdown))
    return {"scored": scored}


async def assemble_node(state: CampaignState, ctx: NodeContext) -> dict[str, Any]:
    by_segment: dict[str, list[ScoredVariant]] = {}
    for sv in state.scored:
        by_segment.setdefault(sv.variant.segment_id, []).append(sv)

    segment_plans: list[SegmentPlan] = []
    for segment in state.brief.segments:
        ranked = sorted(
            by_segment.get(segment.id, []),
            key=lambda sv: sv.score.composite,
            reverse=True,
        )
        if not ranked:
            continue
        segment_plans.append(
            SegmentPlan(
                segment_id=segment.id,
                segment_name=segment.name,
                scored_variants=ranked,
                winner=ranked[0],
                runner_up=ranked[1] if len(ranked) > 1 else None,
            )
        )

    plan = CampaignPlan(
        id=state.request_id,
        goal=state.brief.goal,
        channels=state.brief.channels,
        product_name=state.brief.product_name,
        segment_plans=segment_plans,
        model=state.model_label,
        fallback_count=state.fallback_count,
        degraded=state.fallback_count > 0,
    )
    return {"plan": plan}


# --------------------------------------------------------------------------- #
# Prompt building and parsing
# --------------------------------------------------------------------------- #
def _generate_prompt(brief: Brief, segment: Segment, channel: Channel) -> tuple[str, str]:
    if channel is Channel.EMAIL:
        channel_rules = "Write a subject (<=55 chars), a short preview_text, and an email body."
    else:
        channel_rules = "Keep the body under 160 characters; leave subject and preview_text empty."

    system = (
        "TASK: generate\n"
        "You are an expert lifecycle marketer. Write distinct, on-brand, high-converting "
        f"variants for one audience segment. {channel_rules} Personalize with the "
        "{first_name} merge tag and the segment's traits, and end with a clear call to "
        'action. Respond ONLY as JSON: {"variants": [{"angle": "...", "subject": "...", '
        '"preview_text": "...", "body": "..."}]}.'
    )
    user = "\n".join(
        [
            f"product: {brief.product_name}",
            f"description: {brief.product_description}",
            f"value_props: {'; '.join(brief.value_props)}",
            f"tone: {brief.brand_voice.tone.value}",
            f"goal: {brief.goal.value}",
            f"channel: {channel.value}",
            f"segment: {segment.name}",
            f"traits: {', '.join(segment.traits)}",
            f"incentive: {segment.incentive}",
            f"count: {brief.variants_per_segment}",
        ]
    )
    return system, user


def _parse_variants(raw: str) -> list[dict[str, Any]]:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in generation output")
    data = json.loads(raw[start : end + 1])
    variants = data.get("variants", [])
    if not isinstance(variants, list):
        raise ValueError("'variants' is not a list")
    return [item for item in variants if isinstance(item, dict)]


def _to_variant(segment: Segment, channel: Channel, index: int, item: dict[str, Any]) -> Variant:
    return Variant(
        id=f"{segment.id}:{channel.value}:{index}",
        segment_id=segment.id,
        channel=channel,
        angle=str(item.get("angle", "")),
        subject=str(item.get("subject", "")) if channel is Channel.EMAIL else "",
        preview_text=str(item.get("preview_text", "")) if channel is Channel.EMAIL else "",
        body=str(item.get("body", "")).strip() or "(empty)",
    )


def _fallback_variant(brief: Brief, segment: Segment, channel: Channel) -> dict[str, Any]:
    value = brief.value_props[0] if brief.value_props else brief.product_description
    if channel is Channel.EMAIL:
        return {
            "angle": brief.goal.value,
            "subject": f"{{first_name}}, {value[:40]}",
            "preview_text": value[:80],
            "body": f"Hi {{first_name}},\n\n{value} with {brief.product_name}.\n\nGet started today →",
        }
    return {
        "angle": brief.goal.value,
        "body": f"{{first_name}}, {value[:80]} Get started: ex.co/go",
    }
