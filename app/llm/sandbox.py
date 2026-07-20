"""Deterministic sandbox LLM.

Lets the whole studio run with no model server (CI, offline). It is not a constant
stub: it generates *plausible, varied* marketing copy and judges brand voice using
small heuristics, driven by a ``TASK:`` marker and labeled fields that the pipeline
places in the prompt. Real models treat those as ordinary instructions, so the
seam stays honest. Output is deterministic, which is what makes eval and tests
possible.

The generator intentionally varies CTA strength and personalization across variants
so the scorer produces a meaningful ranking (a real A/B signal).
"""

from __future__ import annotations

import json
import re
import time

from app.domain.enums import TONE_LEXICON, Tone
from app.llm.base import LlmPort
from app.metrics import LLM_CALLS, LLM_LATENCY

_TASK_RE = re.compile(r"TASK:\s*(\w+)", re.IGNORECASE)

# Angle rotations per lifecycle goal. Index by variant number for variety.
_ANGLES: dict[str, list[str]] = {
    "welcome": ["Warm welcome", "Your first win", "A gift to get started"],
    "abandoned_cart": ["You left something behind", "Still deciding?", "Your cart is waiting"],
    "re_engagement": ["We miss you", "Look what's new", "Here's a reason to return"],
    "upsell": ["Unlock more", "Ready for the next level", "Get more out of it"],
    "winback": ["A reason to come back", "We've changed", "One more look"],
    "promotion": ["Limited-time offer", "Save today", "Deal ends soon"],
}
# Strong vs weak calls to action, rotated so variants score differently.
_CTAS = ["Shop now", "Get started today", "Claim your offer", "Learn more", "See what's new"]


class SandboxLlm(LlmPort):
    async def complete(
        self, *, system: str, user: str, json_mode: bool = False, temperature: float = 0.7
    ) -> str:
        task = self._task_of(system) or "unknown"
        started = time.perf_counter()
        try:
            if task == "generate":
                return json.dumps(self._generate(user))
            if task == "judge":
                return json.dumps(self._judge(user))
            return "{}"
        finally:
            LLM_CALLS.labels(task=task, status="ok").inc()
            LLM_LATENCY.labels(task=task).observe(time.perf_counter() - started)

    @staticmethod
    def _task_of(text: str) -> str:
        match = _TASK_RE.search(text)
        return match.group(1).lower() if match else ""

    # -- generation ---------------------------------------------------------- #
    def _generate(self, user: str) -> dict[str, object]:
        fields = _parse_fields(user)
        product = fields.get("product", "our product")
        channel = fields.get("channel", "email")
        goal = fields.get("goal", "re_engagement")
        tone = _as_tone(fields.get("tone", "friendly"))
        incentive = fields.get("incentive", "")
        traits = _split(fields.get("traits", ""))
        value_props = _split(fields.get("value_props", ""))
        count = _int(fields.get("count", "3"), default=3)

        angles = _ANGLES.get(goal, _ANGLES["re_engagement"])
        tone_words = TONE_LEXICON[tone]

        variants: list[dict[str, str]] = []
        for i in range(count):
            angle = angles[i % len(angles)]
            cta = _CTAS[i % len(_CTAS)]
            tone_word = tone_words[i % len(tone_words)]
            value = value_props[i % len(value_props)] if value_props else "everything you need"
            trait = traits[i % len(traits)] if traits else ""
            # Rotate personalization on/off so variants differ in that dimension.
            personalize = i % 2 == 0

            if channel == "sms":
                variants.append(self._sms(product, angle, cta, incentive, personalize))
            else:
                variants.append(
                    self._email(
                        product, angle, cta, tone_word, value, trait, incentive, personalize
                    )
                )
        return {"variants": variants}

    @staticmethod
    def _email(
        product: str,
        angle: str,
        cta: str,
        tone_word: str,
        value: str,
        trait: str,
        incentive: str,
        personalize: bool,
    ) -> dict[str, str]:
        name = "{first_name}" if personalize else "there"
        offer = f" Enjoy {incentive}." if incentive else ""
        trait_line = (
            f" Since you're into {trait}, we think you'll love this."
            if (personalize and trait)
            else ""
        )
        subject = (
            f"{name}, {angle.lower()} at {product}" if personalize else f"{angle} at {product}"
        )
        preview = f"{tone_word.capitalize()} — {value}."
        body = (
            f"Hi {name},\n\n"
            f"{angle}: {value} with {product}.{trait_line}{offer}\n\n"
            f"{cta} →\n\n"
            "— The Team"
        )
        return {
            "angle": angle,
            "subject": subject[:80],
            "preview_text": preview[:120],
            "body": body,
        }

    @staticmethod
    def _sms(
        product: str, angle: str, cta: str, incentive: str, personalize: bool
    ) -> dict[str, str]:
        name = "{first_name}" if personalize else "Hi"
        offer = f" {incentive}." if incentive else ""
        body = f"{name}, {angle.lower()} at {product}.{offer} {cta}: ex.co/go"
        return {"angle": angle, "subject": "", "preview_text": "", "body": body[:160]}

    # -- brand-voice judge (LLM-as-judge) ------------------------------------ #
    def _judge(self, user: str) -> dict[str, object]:
        fields = _parse_fields(user)
        text = fields.get("text", "").lower()
        tone = _as_tone(fields.get("tone", "friendly"))
        banned = _split(fields.get("banned", ""))

        notes: list[str] = []
        score = 0.6

        hit = next((phrase for phrase in banned if phrase and phrase.lower() in text), None)
        if hit:
            score -= 0.5
            notes.append(f"contains banned phrase: {hit}")

        if any(word in text for word in TONE_LEXICON[tone]):
            score += 0.25
            notes.append(f"matches {tone.value} tone")
        else:
            notes.append(f"weak {tone.value} tone signal")

        score = max(0.0, min(1.0, score))
        return {"brand_voice": round(score, 3), "notes": notes}


def _parse_fields(text: str) -> dict[str, str]:
    """Extract 'label: value' lines into a dict (last value wins)."""

    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            label, _, value = line.partition(":")
            key = label.strip().lower()
            if key and " " not in key:
                fields[key] = value.strip()
    return fields


def _split(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[;,]", value) if item.strip()]


def _as_tone(value: str) -> Tone:
    try:
        return Tone(value.strip().lower())
    except ValueError:
        return Tone.FRIENDLY


def _int(value: str, *, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default
