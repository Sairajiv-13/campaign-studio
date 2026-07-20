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

    assert report.n == 18
    # The scorer should rank the human-preferred variant higher on most pairs. It
    # does NOT score 100% — the adversarial pairs expose real failure modes that
    # are documented rather than papered over (docs/EVALUATION.md).
    assert report.accuracy >= 0.8
    # And separate them decisively, not by a coin-flip margin.
    assert report.mean_margin > 0.05

    payload = to_dict(report)
    json.dumps(payload)  # serializable
    # The single-lever levers must all be present; adversarial dimensions add more.
    assert {
        "cta",
        "personalization",
        "deliverability",
        "brand_voice",
        "subject",
        "clarity",
    } <= set(payload["by_dimension"])


async def test_known_failure_modes_are_still_failing() -> None:
    """Pin the documented failure modes.

    These two adversarial pairs are expected to fail: the scorer has no notion of
    whether personalization is appropriate, or whether a clean subject line is
    actually specific. If either starts passing, the scorer improved and
    docs/EVALUATION.md needs updating — that's a result worth noticing, not a
    silent change.
    """

    results = await evaluate(SandboxLlm(), default_pairs())
    failing = {r.id for r in results if not r.correct}
    assert failing == {"a01", "a03"}
