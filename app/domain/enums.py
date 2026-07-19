"""Controlled vocabularies for the campaign domain."""

from __future__ import annotations

from enum import StrEnum


class Channel(StrEnum):
    EMAIL = "email"
    SMS = "sms"


class Goal(StrEnum):
    """The lifecycle stage / intent of the campaign."""

    WELCOME = "welcome"
    ABANDONED_CART = "abandoned_cart"
    RE_ENGAGEMENT = "re_engagement"
    UPSELL = "upsell"
    WINBACK = "winback"
    PROMOTION = "promotion"


class Tone(StrEnum):
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    PLAYFUL = "playful"
    URGENT = "urgent"
    LUXURY = "luxury"


# Lexicon used by the sandbox generator and the brand-voice heuristic to give each
# tone a recognizable surface form. Kept next to the enum so they never drift.
TONE_LEXICON: dict[Tone, list[str]] = {
    Tone.FRIENDLY: ["hey", "we're here", "happy", "love", "thanks"],
    Tone.PROFESSIONAL: ["we're pleased", "please", "regards", "ensure", "review"],
    Tone.PLAYFUL: ["psst", "oops", "treat yourself", "wink", "fun"],
    Tone.URGENT: ["now", "today", "don't miss", "last chance", "ends soon"],
    Tone.LUXURY: ["exclusive", "curated", "crafted", "reserved", "elevated"],
}
