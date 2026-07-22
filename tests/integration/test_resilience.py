"""Generation resilience: a failing model degrades, it doesn't crash (ADR-005).

There's no queue or worker here. Generation is synchronous and bounded, so
"reliability" means one bad completion never sinks the whole campaign, and the plan
reports honestly when it fell back.
"""

from __future__ import annotations

import pytest
from app.graph.build import Pipeline
from app.graph.context import NodeContext
from app.graph.state import CampaignState
from app.llm.base import TransientLlmError
from app.llm.sandbox import SandboxLlm

pytestmark = pytest.mark.integration

_BRIEF = {
    "product_name": "Aurora",
    "product_description": "sleep supplements",
    "value_props": ["fall asleep faster"],
    "brand_voice": {"tone": "friendly"},
    "goal": "welcome",
    "channels": ["email", "sms"],
    "segments": [
        {"id": "a", "name": "A", "traits": ["t1"]},
        {"id": "b", "name": "B", "traits": ["t2"]},
    ],
    "variants_per_segment": 2,
}


class _AlwaysFailGenerateLlm(SandboxLlm):
    """Generation always fails; judging still works so scoring proceeds."""

    async def complete(
        self, *, system: str, user: str, json_mode: bool = False, temperature: float = 0.7
    ) -> str:
        if self._task_of(system) == "generate":
            raise TransientLlmError("model down")
        return await super().complete(
            system=system, user=user, json_mode=json_mode, temperature=temperature
        )


def _state(**over: object) -> CampaignState:
    from app.domain.models import Brief

    return CampaignState(request_id="resil-1", brief=Brief(**{**_BRIEF, **over}))


async def test_generation_failure_falls_back_and_reports_degraded() -> None:
    ctx = NodeContext(llm=_AlwaysFailGenerateLlm(), model_label="sandbox")
    plan = await Pipeline(ctx).run(_state())

    # 2 segments × 2 channels = 4 slots, all fell back.
    assert plan.fallback_count == 4
    assert plan.degraded is True
    # Crucially, a usable plan still came out. Every segment has a winner.
    assert len(plan.segment_plans) == 2
    for sp in plan.segment_plans:
        assert sp.winner.variant.body


async def test_healthy_generation_reports_no_degradation() -> None:
    ctx = NodeContext(llm=SandboxLlm(), model_label="sandbox")
    plan = await Pipeline(ctx).run(_state())
    assert plan.fallback_count == 0
    assert plan.degraded is False
