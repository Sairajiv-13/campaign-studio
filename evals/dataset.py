"""Labeled A/B copy pairs with a human-preferred winner.

Each pair holds two variants for the same context and the variant a marketer
prefers, with the reason. A good scorer should rank the preferred variant higher.
The pairs isolate one lever at a time (CTA, personalization, deliverability, brand
voice, subject, clarity): the preferred variant is genuinely stronger on that lever
and the other is weaker on exactly it. The winning side alternates between A and B
so a position-biased baseline scores only ~50%.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Reusable copy fragments so pairs stay readable and the "which side wins" is
# obvious. STRONG_* is good copy; WEAK_* is deliberately worse on one lever.
_STRONG_CTA = (
    "Hi {first_name},\n\nYou left something great behind. Complete your order today.\n\nShop now →"
)
_WEAK_CTA = (
    "Hi {first_name},\n\nYou left something behind. You can read about it whenever.\n\nLearn more"
)
_STRONG_PERSONAL = (
    "Hi {first_name},\n\nSince you love running, we lined up gear you'll want. Get yours today →"
)
_WEAK_PERSONAL = "Hello,\n\nWe have some products available. See more"
_CLEAN = "Hi {first_name},\n\nWe've improved a few things since you left. Reactivate anytime.\n\nGet started →"
_SPAMMY = "CONGRATS {first_name}!!! You're a WINNER!!! 100% FREE cash bonus — click here now!!! Guaranteed!!!"
_ONBRAND_LUX = (
    "{first_name}, an exclusive preview crafted for you — reserved early access. Explore now →"
)
_OFFBRAND = "Hey!! grab this miracle cure super cheap lol, don't miss out!!"
_CLEAR = "Hi {first_name},\n\nTeams ship faster with our tool. Here's a two-minute overview.\n\nSee how →"
_MUDDY = "Hi, so basically the reason we are reaching out today is because there are many things that our platform which is very comprehensive can do for organizations like yours in numerous ways that are honestly hard to summarize."


@dataclass(frozen=True)
class EvalPair:
    id: str
    dimension: str
    channel: str
    tone: str
    traits: list[str]
    a_subject: str
    a_body: str
    b_subject: str
    b_body: str
    preferred: str  # "a" or "b"
    reason: str
    banned: list[str] = field(default_factory=list)


PAIRS: list[EvalPair] = [
    EvalPair(
        "p01",
        "cta",
        "email",
        "friendly",
        ["added to cart"],
        "{first_name}, your cart is waiting",
        _STRONG_CTA,
        "{first_name}, your cart is waiting",
        _WEAK_CTA,
        "a",
        "Strong, specific CTA beats a passive 'learn more'.",
    ),
    EvalPair(
        "p02",
        "personalization",
        "email",
        "friendly",
        ["frequent buyer", "loves running"],
        "A selection for you",
        _WEAK_PERSONAL,
        "{first_name}, picked for you",
        _STRONG_PERSONAL,
        "b",
        "Merge tag + segment trait reference lifts relevance.",
    ),
    EvalPair(
        "p03",
        "deliverability",
        "email",
        "professional",
        ["former subscriber"],
        "A quick update on your account",
        _CLEAN,
        "100% FREE!!! ACT NOW",
        _SPAMMY,
        "a",
        "The second reeks of spam triggers and lands in junk.",
    ),
    EvalPair(
        "p04",
        "brand_voice",
        "email",
        "luxury",
        ["high lifetime value"],
        "cheap deals inside",
        _OFFBRAND,
        "An exclusive, curated preview",
        _ONBRAND_LUX,
        "b",
        "On-brand luxury tone vs off-brand copy with a banned phrase.",
        ["miracle cure"],
    ),
    EvalPair(
        "p05",
        "subject",
        "email",
        "friendly",
        ["just joined"],
        "{first_name}, welcome — here's your first win",
        _CLEAR,
        "WELCOME BUY NOW SIGN UP TODAY LIMITED OFFER DON'T MISS OUT ACT NOW",
        _CLEAR,
        "a",
        "Same body; A's subject is well-formed, B's is a shouting run-on.",
    ),
    EvalPair(
        "p06",
        "cta",
        "email",
        "urgent",
        ["cart abandoner"],
        "{first_name}, ends tonight",
        "Your cart may expire at some point. You could look at it if you want.",
        "{first_name}, ends tonight",
        "Your cart expires at midnight. Claim your 10% off now →",
        "b",
        "Clear urgency + claim CTA outperforms vague phrasing.",
    ),
    EvalPair(
        "p07",
        "personalization",
        "sms",
        "friendly",
        ["inactive 60 days"],
        "",
        "{first_name}, we saved your spot. Come back for 20% off: ex.co/go",
        "",
        "Hello. There is a discount available. Visit our website.",
        "a",
        "Personalized, concrete SMS beats a generic one.",
    ),
    EvalPair(
        "p08",
        "deliverability",
        "sms",
        "friendly",
        [],
        "",
        "FREE MONEY!!! ACT NOW!!! CLICK HERE $$$ ex.co/go",
        "",
        "{first_name}, your order ships free today. Finish up: ex.co/go",
        "b",
        "Spammy SMS damages deliverability and trust.",
    ),
    EvalPair(
        "p09",
        "clarity",
        "email",
        "professional",
        ["evaluating options"],
        "How teams use our platform",
        _CLEAR,
        "Re: the thing",
        _MUDDY,
        "a",
        "Concise, readable copy beats a convoluted run-on.",
    ),
    EvalPair(
        "p10",
        "brand_voice",
        "email",
        "playful",
        ["loves deals"],
        "Formal notice regarding your account status",
        "Dear valued customer, please be advised that a promotional consideration has been applied per our terms.",
        "psst… a little treat for you",
        "{first_name}, treat yourself! We saved a fun surprise in your account. Grab it →",
        "b",
        "Playful brand voice vs stiff, off-tone corporate copy.",
    ),
    EvalPair(
        "p11",
        "cta",
        "email",
        "friendly",
        ["upsell candidate"],
        "{first_name}, unlock more",
        "You're getting great results. Upgrade now to unlock advanced features →",
        "{first_name}, unlock more",
        "You're getting great results. There is a higher tier that exists.",
        "a",
        "Actionable upgrade CTA beats a flat statement.",
    ),
    EvalPair(
        "p12",
        "personalization",
        "email",
        "friendly",
        ["bought running shoes"],
        "You might like these",
        "Hello,\n\nHere are some products. Buy now if interested.",
        "Perfect with your running shoes",
        "Hi {first_name},\n\nBased on your running shoes, these socks are a match. Shop now →",
        "b",
        "Explicit tie to a past purchase raises relevance and CTA quality.",
    ),
]
