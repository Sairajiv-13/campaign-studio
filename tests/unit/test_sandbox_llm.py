"""Unit tests for the deterministic sandbox model."""

from __future__ import annotations

import json

from app.llm.sandbox import SandboxLlm

_GEN_SYSTEM = 'TASK: generate\nReturn JSON {"variants":[...]}'
_GEN_USER = "\n".join(
    [
        "product: Aurora",
        "description: sleep supplements",
        "value_props: fall asleep faster; no grogginess",
        "tone: friendly",
        "goal: abandoned_cart",
        "channel: email",
        "segment: Cart abandoners",
        "traits: added to cart, browsed sleep",
        "incentive: 10% off",
        "count: 3",
    ]
)


async def test_generate_returns_requested_variant_count() -> None:
    raw = await SandboxLlm().complete(system=_GEN_SYSTEM, user=_GEN_USER, json_mode=True)
    data = json.loads(raw)
    assert len(data["variants"]) == 3
    first = data["variants"][0]
    assert first["body"]
    assert first["subject"]  # email has a subject


async def test_generate_is_deterministic() -> None:
    llm = SandboxLlm()
    a = await llm.complete(system=_GEN_SYSTEM, user=_GEN_USER, json_mode=True)
    b = await llm.complete(system=_GEN_SYSTEM, user=_GEN_USER, json_mode=True)
    assert a == b


async def test_generate_sms_has_no_subject_and_is_short() -> None:
    user = _GEN_USER.replace("channel: email", "channel: sms")
    raw = await SandboxLlm().complete(system=_GEN_SYSTEM, user=user, json_mode=True)
    for variant in json.loads(raw)["variants"]:
        assert variant["subject"] == ""
        assert len(variant["body"]) <= 160


async def test_judge_penalizes_banned_phrase() -> None:
    system = "TASK: judge\n..."
    user = "tone: friendly\nbanned: miracle cure\nguidelines:\ntext: try this miracle cure now"
    raw = await SandboxLlm().complete(system=system, user=user, json_mode=True)
    data = json.loads(raw)
    assert data["brand_voice"] <= 0.2


async def test_unknown_task_returns_empty_object() -> None:
    assert await SandboxLlm().complete(system="no task here", user="x") == "{}"
