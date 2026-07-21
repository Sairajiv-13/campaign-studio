"""A hard brand-safety flag keeps a variant from winning its segment (ADR-007).

Proves the wiring: the guardrail runs in the pipeline and assemble ranks a clean
variant above a hard-flagged one even when the flagged one scores higher.
"""

from __future__ import annotations

import pytest
from app.domain.enums import Channel
from app.domain.models import (
    ScoreBreakdown,
    ScoredVariant,
    Segment,
    Variant,
)
from app.graph.nodes import assemble_node
from app.graph.state import CampaignState

pytestmark = pytest.mark.integration


def _scored(vid: str, composite: float, *, banned: bool) -> ScoredVariant:
    variant = Variant(
        id=vid,
        segment_id="s1",
        channel=Channel.EMAIL,
        subject="Hi",
        body="This miracle cure helps." if banned else "A gentle nudge to come back.",
    )
    score = ScoreBreakdown(
        brand_voice=composite,
        clarity=composite,
        cta_strength=composite,
        personalization=composite,
        deliverability=composite,
        composite=composite,
    )
    from app.domain.models import BrandVoice
    from app.guardrails import check_variant

    flags = check_variant(variant, brand_voice=BrandVoice(banned_phrases=["miracle cure"]))
    return ScoredVariant(variant=variant, score=score, flags=flags)


async def test_clean_variant_beats_higher_scoring_flagged_one() -> None:
    # The flagged variant scores higher (0.9) than the clean one (0.5), but a hard
    # banned-phrase flag must drop it below the clean variant.
    flagged = _scored("bad", 0.9, banned=True)
    clean = _scored("good", 0.5, banned=False)
    assert flagged.has_hard_flag and not clean.has_hard_flag

    state = CampaignState(
        request_id="r1",
        brief={  # type: ignore[arg-type]
            "product_name": "Aurora",
            "product_description": "x",
            "segments": [Segment(id="s1", name="S1")],
        },
        scored=[flagged, clean],
    )
    result = await assemble_node(state, ctx=None)  # type: ignore[arg-type]
    plan = result["plan"]
    winner = plan.segment_plans[0].winner
    assert winner.variant.id == "good", "a hard-flagged variant must not win"
