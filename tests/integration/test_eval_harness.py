"""The scorer eval against the sandbox judge — doubles as a regression gate."""

from __future__ import annotations

import json

import pytest
from app.llm.sandbox import SandboxLlm
from evals.harness import default_pairs, evaluate, to_dict
from evals.metrics import build_report

pytestmark = pytest.mark.integration


async def test_scorer_agrees_with_human_preference() -> None:
    results = await evaluate(SandboxLlm(), default_pairs())
    report = build_report(results)

    assert report.n == 12
    # The scorer should rank the human-preferred variant higher on most pairs.
    assert report.accuracy >= 0.8
    # And separate them decisively, not by a coin-flip margin.
    assert report.mean_margin > 0.05

    payload = to_dict(report)
    json.dumps(payload)  # serializable
    assert set(payload["by_dimension"]) <= {
        "cta",
        "personalization",
        "deliverability",
        "brand_voice",
        "subject",
        "clarity",
    }
