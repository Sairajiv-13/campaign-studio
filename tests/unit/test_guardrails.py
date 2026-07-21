"""Brand-safety guardrail unit tests (ADR-007)."""

from __future__ import annotations

from app.domain.enums import Channel
from app.domain.models import BrandVoice, Variant
from app.guardrails import check_variant
from evals.guardrails import CLEAN, POISONED


def _sms(body: str) -> Variant:
    return Variant(id="v", segment_id="s", channel=Channel.SMS, body=body)


def _email(subject: str, body: str) -> Variant:
    return Variant(id="v", segment_id="s", channel=Channel.EMAIL, subject=subject, body=body)


def test_clean_email_has_no_hard_flags() -> None:
    flags = check_variant(
        _email("Welcome to Aurora", "Hi {first_name}, thanks for joining us today."),
        brand_voice=BrandVoice(),
    )
    assert not any(f.severity == "hard" for f in flags)


def test_sms_over_limit_is_hard_flagged() -> None:
    flags = check_variant(_sms("x" * 200), brand_voice=BrandVoice())
    assert any(f.rule == "sms_length" and f.severity == "hard" for f in flags)


def test_unknown_merge_tag_is_hard_flagged() -> None:
    flags = check_variant(_email("Hi", "Hello {frist_name}, welcome!"), brand_voice=BrandVoice())
    assert any(f.rule == "merge_tag" and f.severity == "hard" for f in flags)


def test_allowed_merge_tags_pass() -> None:
    flags = check_variant(
        _email("Hi", "Hi {first_name}, your {product} order from {last_name} co."),
        brand_voice=BrandVoice(),
    )
    assert not any(f.rule == "merge_tag" for f in flags)


def test_banned_phrase_is_hard_flagged() -> None:
    flags = check_variant(
        _email("Hi", "This miracle cure is for you."),
        brand_voice=BrandVoice(banned_phrases=["miracle cure"]),
    )
    assert any(f.rule == "banned_phrase" and f.severity == "hard" for f in flags)


def test_spam_and_caps_are_soft_flags() -> None:
    flags = check_variant(
        _email("ACT NOW WINNER", "Click here, this is 100% free and guaranteed!"),
        brand_voice=BrandVoice(),
    )
    rules = {f.rule for f in flags}
    assert "spam_trigger" in rules
    assert all(f.severity == "soft" for f in flags if f.rule in {"spam_trigger", "all_caps"})


def test_every_poisoned_case_is_caught() -> None:
    for case in POISONED:
        flags = check_variant(case.variant, brand_voice=case.brand_voice)
        assert any(
            f.severity == "hard" and f.rule == case.expect_rule for f in flags
        ), f"missed {case.id}: {case.note}"


def test_clean_control_passes() -> None:
    flags = check_variant(CLEAN.variant, brand_voice=CLEAN.brand_voice)
    assert not any(f.severity == "hard" for f in flags)
