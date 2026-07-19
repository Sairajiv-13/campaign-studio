"""Unit tests for the deterministic marketing heuristics."""

from __future__ import annotations

from app.scoring.heuristics import (
    count_syllables,
    cta_strength,
    deliverability,
    personalization,
    readability,
    subject_quality,
)


def test_readability_prefers_simple_prose() -> None:
    simple = readability("Buy now. It is great. You will love it.")
    complex_ = readability(
        "Notwithstanding the aforementioned considerations, the comprehensive "
        "implementation necessitates substantial organizational recalibration."
    )
    assert simple > complex_
    assert 0.0 <= complex_ <= 1.0 and 0.0 <= simple <= 1.0


def test_count_syllables() -> None:
    assert count_syllables("cat") == 1
    assert count_syllables("marketing") == 3
    assert count_syllables("make") == 1  # silent e


def test_cta_strength_ranks_strong_over_weak_over_none() -> None:
    strong = cta_strength("Shop now →")
    weak = cta_strength("Learn more about it")
    none = cta_strength("Here is some information.")
    assert strong > weak > none


def test_deliverability_penalizes_spam() -> None:
    clean = deliverability("Your order ships free today. Finish checkout.")
    spam = deliverability("FREE MONEY!!! ACT NOW!!! CLICK HERE $$$ guaranteed!!!")
    assert clean > 0.8
    assert spam < 0.4


def test_personalization_rewards_merge_tag_and_traits() -> None:
    high = personalization("Hi {first_name}, since you love running, shop now.", ["running"])
    low = personalization("Hello, check out our products.", ["running"])
    assert high > low
    assert high >= 0.6


def test_subject_quality_ranges() -> None:
    good = subject_quality("{first_name}, your cart is waiting")
    shouting = subject_quality("BUY NOW ACT NOW LIMITED OFFER DON'T MISS OUT TODAY ONLY")
    empty = subject_quality("")  # SMS has no subject; must not penalize
    assert good > shouting
    assert empty == 1.0
