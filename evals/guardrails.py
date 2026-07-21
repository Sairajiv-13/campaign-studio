"""Adversarial corpus for the brand-safety guardrail (ADR-007).

The scorer eval measures ranking judgment; this measures whether the guardrail
catches *known-bad copy* — the outputs a real model produces on a bad day. Each
case is a variant the guardrail must hard-flag; the runner reports a catch rate and
CI gates on it. A regression that weakens a rule shows up as a dropped catch.

Only failure modes a rule can defend deterministically live here (length, merge
tags, banned phrases) — not "is the tone right", which we don't pretend to judge.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import Channel
from app.domain.models import BrandVoice, Variant


@dataclass(frozen=True)
class GuardrailCase:
    id: str
    variant: Variant
    brand_voice: BrandVoice
    expect_rule: str  # the hard rule this case must trip
    note: str = ""


def _sms(id: str, body: str) -> Variant:
    return Variant(id=id, segment_id="s", channel=Channel.SMS, body=body)


def _email(id: str, subject: str, body: str) -> Variant:
    return Variant(id=id, segment_id="s", channel=Channel.EMAIL, subject=subject, body=body)


# Every case MUST produce a hard flag of `expect_rule`.
POISONED: list[GuardrailCase] = [
    GuardrailCase(
        "g01",
        _sms(
            "g01", "Hi {first_name}, " + "grab our amazing new bundle deal today and save big! " * 4
        ),
        BrandVoice(),
        "sms_length",
        "SMS well over 160 chars",
    ),
    GuardrailCase(
        "g02",
        _email("g02", "Welcome", "Hi {frist_name}, thanks for joining — here's your gift."),
        BrandVoice(),
        "merge_tag",
        "typo'd merge tag renders literally",
    ),
    GuardrailCase(
        "g03",
        _email("g03", "A note", "This miracle cure will change your life, {first_name}."),
        BrandVoice(banned_phrases=["miracle cure"]),
        "banned_phrase",
        "compliance-banned phrase",
    ),
    GuardrailCase(
        "g04",
        _sms("g04", "{first_name}, unlock {reward} now with code {promo_code}."),
        BrandVoice(),
        "merge_tag",
        "multiple unknown merge tags",
    ),
]


# A clean control the guardrail must NOT hard-flag, to catch an over-eager rule.
CLEAN = GuardrailCase(
    "clean",
    _email(
        "clean",
        "Welcome to Aurora",
        "Hi {first_name}, thanks for joining. Here's a little something to get you started.",
    ),
    BrandVoice(),
    expect_rule="",
    note="legitimate copy — must pass",
)


def guardrail_catch_rate() -> tuple[float, int]:
    """Fraction of poisoned cases the guardrail hard-flags (and the clean control
    must pass). Deterministic — no model — so it's cheap and gates every run."""

    from app.guardrails import check_variant

    caught = 0
    for case in POISONED:
        flags = check_variant(case.variant, brand_voice=case.brand_voice)
        if any(f.severity == "hard" and f.rule == case.expect_rule for f in flags):
            caught += 1
    clean_flags = check_variant(CLEAN.variant, brand_voice=CLEAN.brand_voice)
    clean_ok = not any(f.severity == "hard" for f in clean_flags)
    rate = caught / len(POISONED) if POISONED else 1.0
    return (rate if clean_ok else 0.0, len(POISONED))
