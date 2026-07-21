"""Brand-safety and compliance guardrails on generated marketing copy.

Generated copy goes in front of real customers and through real email/SMS
infrastructure, so before a variant can *win* its segment it passes a deterministic
gate (ADR-007). These are rule-based checks — regex and length, no model judging a
model — because the failure modes that actually hurt are mechanical and objective:

- an SMS over the segment limit gets split (extra cost) or truncated by the carrier;
- a broken ``{merge_tag}`` renders literally in the customer's inbox;
- a banned/off-brand phrase is a compliance problem;
- spam-trigger words and SHOUTING tank deliverability.

A "hard" flag drops a variant below clean ones in ranking; "soft" flags are
advisory. We deliberately don't try to judge tone or truthfulness here — a rule
can't, and the brand-voice *score* already covers tone.
"""

from __future__ import annotations

import re

from app.domain.enums import Channel
from app.domain.models import BrandVoice, GuardrailFlag, Variant

# Carriers split an SMS past 160 GSM-7 chars into multiple billable segments.
SMS_MAX_CHARS = 160
# Most inboxes truncate a subject past ~60 chars; past 80 it's certainly cut.
SUBJECT_MAX_CHARS = 80

# Only these merge tags are supported by the (hypothetical) send layer. Anything
# else would ship an unrendered literal to the customer.
ALLOWED_MERGE_TAGS = {"first_name", "last_name", "product"}

# Classic spam-trigger phrases that hurt deliverability. Lowercased substring match.
_SPAM_PHRASES = (
    "act now",
    "click here",
    "100% free",
    "risk free",
    "guaranteed",
    "winner",
    "cash bonus",
    "no cost",
    "limited time only",
)
_MERGE_TAG_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_CAPS_WORD_RE = re.compile(r"\b[A-Z]{4,}\b")


def _text_of(variant: Variant) -> str:
    return " ".join(part for part in (variant.subject, variant.preview_text, variant.body) if part)


def check_variant(variant: Variant, *, brand_voice: BrandVoice) -> list[GuardrailFlag]:
    """Run every rule against one variant and return the flags it trips."""

    flags: list[GuardrailFlag] = []
    text = _text_of(variant)
    lowered = text.lower()

    # --- length (hard: mechanical failure) --- #
    if variant.channel is Channel.SMS and len(variant.body) > SMS_MAX_CHARS:
        flags.append(
            GuardrailFlag(
                rule="sms_length",
                severity="hard",
                message=f"SMS body is {len(variant.body)} chars (limit {SMS_MAX_CHARS})",
            )
        )
    if variant.channel is Channel.EMAIL and len(variant.subject) > SUBJECT_MAX_CHARS:
        flags.append(
            GuardrailFlag(
                rule="subject_length",
                severity="soft",
                message=f"subject is {len(variant.subject)} chars (limit {SUBJECT_MAX_CHARS})",
            )
        )

    # --- merge tags (hard: renders literally to the customer) --- #
    unknown = sorted({t for t in _MERGE_TAG_RE.findall(text) if t not in ALLOWED_MERGE_TAGS})
    if unknown:
        flags.append(
            GuardrailFlag(
                rule="merge_tag",
                severity="hard",
                message=f"unknown merge tag(s): {', '.join('{' + t + '}' for t in unknown)}",
            )
        )

    # --- banned phrases (hard: compliance / off-brand) --- #
    banned_hit = sorted({p for p in brand_voice.banned_phrases if p and p.lower() in lowered})
    if banned_hit:
        flags.append(
            GuardrailFlag(
                rule="banned_phrase",
                severity="hard",
                message=f"contains banned phrase(s): {', '.join(banned_hit)}",
            )
        )

    # --- spam triggers (soft: deliverability risk) --- #
    spam_hit = sorted({p for p in _SPAM_PHRASES if p in lowered})
    if spam_hit:
        flags.append(
            GuardrailFlag(
                rule="spam_trigger",
                severity="soft",
                message=f"spam-trigger phrase(s): {', '.join(spam_hit)}",
            )
        )

    # --- shouting (soft) --- #
    caps_words = _CAPS_WORD_RE.findall(text)
    if len(caps_words) >= 2:
        flags.append(
            GuardrailFlag(
                rule="all_caps",
                severity="soft",
                message=f"{len(caps_words)} all-caps words read as shouting",
            )
        )

    return flags
