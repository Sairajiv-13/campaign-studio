"""End-to-end pipeline test over the sandbox model (no infrastructure)."""

from __future__ import annotations

import pytest
from app.domain.enums import Channel, Goal, Tone
from app.domain.models import BrandVoice, Brief, Segment
from app.graph.build import Pipeline
from app.graph.context import NodeContext
from app.graph.state import CampaignState
from app.llm.sandbox import SandboxLlm

pytestmark = pytest.mark.integration


def _brief() -> Brief:
    return Brief(
        product_name="Aurora",
        product_description="sleep and focus supplements",
        value_props=["fall asleep faster", "no grogginess"],
        brand_voice=BrandVoice(tone=Tone.FRIENDLY, banned_phrases=["miracle cure"]),
        goal=Goal.ABANDONED_CART,
        channels=[Channel.EMAIL, Channel.SMS],
        segments=[
            Segment(
                id="cart", name="Cart abandoners", traits=["added to cart"], incentive="10% off"
            ),
            Segment(id="churned", name="Churned", traits=["inactive 60 days"], incentive="20% off"),
        ],
        variants_per_segment=3,
    )


async def test_pipeline_produces_ranked_plan() -> None:
    pipeline = Pipeline(NodeContext(llm=SandboxLlm(), model_label="sandbox"))
    plan = await pipeline.run(CampaignState(request_id="c1", brief=_brief()))

    assert plan.model == "sandbox"
    assert len(plan.segment_plans) == 2
    for sp in plan.segment_plans:
        # email + sms x 3 variants = 6 per segment.
        assert len(sp.scored_variants) == 6
        # Winner is the highest composite, and the list is sorted descending.
        composites = [sv.score.composite for sv in sp.scored_variants]
        assert composites == sorted(composites, reverse=True)
        assert sp.winner.score.composite == composites[0]
        assert sp.runner_up is not None


async def test_pipeline_is_deterministic() -> None:
    pipeline = Pipeline(NodeContext(llm=SandboxLlm(), model_label="sandbox"))
    a = await pipeline.run(CampaignState(request_id="c1", brief=_brief()))
    b = await pipeline.run(CampaignState(request_id="c1", brief=_brief()))
    assert a.segment_plans[0].winner.variant.body == b.segment_plans[0].winner.variant.body
