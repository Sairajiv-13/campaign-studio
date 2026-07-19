"""Composite copy scorer.

Blends the deterministic marketing heuristics with an **LLM-as-judge** brand-voice
score into a single weighted composite per variant. The judge call degrades
gracefully: on any LLM failure or malformed output we fall back to a deterministic
banned-phrase check rather than failing the whole campaign.

Weights reflect what actually drives lifecycle performance — brand consistency and
a strong, personalized call to action matter most; deliverability is a floor you
must not sink through.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.domain.enums import Channel
from app.domain.models import BrandVoice, ScoreBreakdown, Variant
from app.llm.base import LlmAdapterError, LlmPort, TransientLlmError
from app.logging import get_logger
from app.scoring.heuristics import (
    cta_strength,
    deliverability,
    personalization,
    readability,
    subject_quality,
)

logger = get_logger(__name__)

WEIGHTS: dict[str, float] = {
    "brand_voice": 0.25,
    "clarity": 0.20,
    "cta_strength": 0.20,
    "personalization": 0.20,
    "deliverability": 0.15,
}


async def score_variant(
    llm: LlmPort, variant: Variant, brand_voice: BrandVoice, traits: list[str]
) -> ScoreBreakdown:
    clarity = _clarity(variant)
    cta = round(cta_strength(variant.body), 4)
    personal = round(personalization(f"{variant.subject} {variant.body}", traits), 4)
    deliver = round(deliverability(variant.body, variant.subject), 4)
    bv_score, notes = await _judge_brand_voice(llm, variant, brand_voice)

    dims = {
        "brand_voice": bv_score,
        "clarity": clarity,
        "cta_strength": cta,
        "personalization": personal,
        "deliverability": deliver,
    }
    composite = round(sum(WEIGHTS[name] * value for name, value in dims.items()), 4)

    if cta < 0.5:
        notes.append("weak or missing call to action")
    if personal < 0.4:
        notes.append("low personalization (no merge tag or segment reference)")
    if deliver < 0.7:
        notes.append("deliverability risk (spam signals)")

    return ScoreBreakdown(
        brand_voice=round(bv_score, 4),
        clarity=clarity,
        cta_strength=cta,
        personalization=personal,
        deliverability=deliver,
        composite=composite,
        notes=notes,
    )


def _clarity(variant: Variant) -> float:
    body_readability = readability(variant.body)
    if variant.channel is Channel.EMAIL:
        return round(0.6 * body_readability + 0.4 * subject_quality(variant.subject), 4)
    brevity = 1.0 if len(variant.body) <= 160 else 0.5
    return round(0.7 * body_readability + 0.3 * brevity, 4)


async def _judge_brand_voice(
    llm: LlmPort, variant: Variant, brand_voice: BrandVoice
) -> tuple[float, list[str]]:
    system = (
        "TASK: judge\n"
        "You are a brand-voice reviewer. Rate how well the marketing copy matches the "
        "brand tone and honors the rules. Respond ONLY as JSON: "
        '{"brand_voice": 0.0, "notes": ["..."]}.'
    )
    flat = " ".join(f"{variant.subject} {variant.body}".split())
    user = (
        f"tone: {brand_voice.tone.value}\n"
        f"banned: {'; '.join(brand_voice.banned_phrases)}\n"
        f"guidelines: {brand_voice.guidelines}\n"
        f"text: {flat}"
    )

    for attempt in range(2):
        try:
            raw = await llm.complete(system=system, user=user, json_mode=True, temperature=0.0)
            data = _parse_json_object(raw)
            score = max(0.0, min(1.0, float(data["brand_voice"])))
            notes = [str(note) for note in data.get("notes", [])][:4]
            return score, notes
        except TransientLlmError:
            if attempt == 0:
                await asyncio.sleep(0.1)
                continue
            break
        except (LlmAdapterError, ValueError, KeyError, TypeError) as exc:
            logger.warning("brand_voice_judge_failed", extra={"detail": str(exc)})
            break

    # Graceful fallback: deterministic banned-phrase check only.
    text = f"{variant.subject} {variant.body}".lower()
    if any(phrase.lower() in text for phrase in brand_voice.banned_phrases if phrase):
        return 0.1, ["brand-voice judge unavailable; banned phrase present"]
    return 0.5, ["brand-voice judge unavailable; neutral score applied"]


def _parse_json_object(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in judge output")
    result: dict[str, Any] = json.loads(text[start : end + 1])
    return result
