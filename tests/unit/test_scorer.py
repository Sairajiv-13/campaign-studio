"""Unit tests for the composite scorer and LLM-as-judge fallback."""

from __future__ import annotations

from app.domain.enums import Channel, Tone
from app.domain.models import BrandVoice, Variant
from app.llm.base import LlmPort, PermanentLlmError
from app.llm.sandbox import SandboxLlm
from app.scoring.scorer import score_variant


def _variant(subject: str, body: str) -> Variant:
    return Variant(id="v1", segment_id="s1", channel=Channel.EMAIL, subject=subject, body=body)


async def test_score_variant_produces_bounded_composite() -> None:
    variant = _variant(
        "{first_name}, your cart is waiting",
        "Hi {first_name},\n\nYou love running — finish your order.\n\nShop now →",
    )
    score = await score_variant(SandboxLlm(), variant, BrandVoice(tone=Tone.FRIENDLY), ["running"])
    for value in (
        score.brand_voice,
        score.clarity,
        score.cta_strength,
        score.personalization,
        score.deliverability,
        score.composite,
    ):
        assert 0.0 <= value <= 1.0
    assert score.cta_strength > 0.5  # strong CTA present
    assert score.personalization > 0.5  # merge tag + trait


async def test_strong_copy_outscores_weak_copy() -> None:
    strong = _variant("{first_name}, ends tonight", "Claim your 10% off now →")
    weak = _variant("re: stuff", "There is a thing you could maybe look at eventually.")
    s = await score_variant(SandboxLlm(), strong, BrandVoice(), [])
    w = await score_variant(SandboxLlm(), weak, BrandVoice(), [])
    assert s.composite > w.composite


async def test_banned_phrase_tanks_brand_voice() -> None:
    variant = _variant("A deal", "Try this miracle cure today!")
    score = await score_variant(
        SandboxLlm(), variant, BrandVoice(banned_phrases=["miracle cure"]), []
    )
    assert score.brand_voice <= 0.2


class _FailingLlm(LlmPort):
    async def complete(
        self, *, system: str, user: str, json_mode: bool = False, temperature: float = 0.7
    ) -> str:
        raise PermanentLlmError("judge down")


async def test_judge_failure_degrades_gracefully() -> None:
    variant = _variant("Hello", "A perfectly fine message. Shop now →")
    score = await score_variant(_FailingLlm(), variant, BrandVoice(), [])
    # Judge unavailable -> neutral brand voice, but scoring still completes.
    assert score.brand_voice == 0.5
    assert 0.0 <= score.composite <= 1.0


async def test_judge_failure_still_catches_banned_phrase() -> None:
    variant = _variant("Hi", "Buy our miracle cure now →")
    score = await score_variant(
        _FailingLlm(), variant, BrandVoice(banned_phrases=["miracle cure"]), []
    )
    assert score.brand_voice <= 0.2
