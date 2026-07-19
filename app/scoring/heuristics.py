"""Deterministic marketing-copy heuristics.

These encode marketing best-practices as pure, testable functions returning a
score in [0, 1]. They are the non-LLM half of the scorer: readability, call-to-
action strength, spam/deliverability risk, personalization, and subject-line
quality. Nothing here calls a model, so it is fast, free, and unit-testable.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z']+")
_SENTENCE_RE = re.compile(r"[.!?]+")

# Strong (imperative + specific) vs weak calls to action.
_STRONG_CTA = (
    "shop now",
    "get started",
    "buy now",
    "sign up",
    "claim your",
    "claim",
    "start now",
    "order today",
    "redeem",
    "upgrade now",
    "get yours",
    "join now",
    "try it free",
    "try now",
)
_WEAK_CTA = ("learn more", "see more", "read more", "find out", "discover", "explore", "check out")

# Classic spam / deliverability-risk triggers (kept distinct from CTAs).
_SPAM_PHRASES = (
    "free money",
    "act now",
    "100% free",
    "risk-free",
    "risk free",
    "you're a winner",
    "click here",
    "$$$",
    "guarantee",
    "cash bonus",
    "no cost",
    "this isn't spam",
    "earn extra cash",
    "double your",
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def count_syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1  # common silent 'e'
    return max(1, count)


def readability(text: str) -> float:
    """Flesch reading ease, normalized to [0, 1] (higher = easier to read)."""

    words = _WORD_RE.findall(text)
    if not words:
        return 0.0
    sentences = max(1, len(_SENTENCE_RE.findall(text)))
    syllables = sum(count_syllables(w) for w in words)
    flesch = 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))
    return _clamp(flesch / 100.0)


def cta_strength(text: str) -> float:
    lowered = text.lower()
    if any(phrase in lowered for phrase in _STRONG_CTA):
        base = 0.85
    elif any(phrase in lowered for phrase in _WEAK_CTA):
        base = 0.5
    else:
        base = 0.1
    if "→" in text or "»" in text:
        base += 0.1
    return _clamp(base)


def deliverability(body: str, subject: str = "") -> float:
    """1 - spam risk. Penalizes spam phrases, shouting caps, and exclamation spam."""

    combined = f"{subject}\n{body}"
    lowered = combined.lower()
    risk = 0.0
    risk += 0.25 * sum(1 for phrase in _SPAM_PHRASES if phrase in lowered)

    words = _WORD_RE.findall(combined)
    if words:
        shouting = sum(1 for w in words if len(w) >= 3 and w.isupper())
        caps_ratio = shouting / len(words)
        if caps_ratio > 0.15:
            risk += min(0.4, caps_ratio)

    exclamations = combined.count("!")
    if exclamations > 2:
        risk += 0.2
    if exclamations > 4 or "!!!" in combined:
        risk += 0.2

    return _clamp(1.0 - risk)


def personalization(text: str, traits: list[str]) -> float:
    lowered = text.lower()
    score = 0.0
    if "{first_name}" in lowered or "{name}" in lowered:
        score += 0.4
    if any(trait.lower() in lowered for trait in traits if trait):
        score += 0.3
    if re.search(r"\byou\b|\byour\b", lowered):
        score += 0.2
    return _clamp(score)


def subject_quality(subject: str) -> float:
    """Email subject-line best practices. Returns 1.0 for an empty subject
    (SMS has none) so it never penalizes channels without one."""

    if not subject:
        return 1.0
    length = len(subject)
    if 20 <= length <= 55:
        score = 1.0
    elif length < 20:
        score = 0.5 + length / 40.0
    else:  # too long -> truncation in inbox
        score = max(0.3, 1.0 - (length - 55) / 60.0)
    if subject.isupper():
        score -= 0.4
    if any(phrase in subject.lower() for phrase in _SPAM_PHRASES):
        score -= 0.3
    if "{first_name}" in subject.lower():
        score += 0.1
    return _clamp(score)
