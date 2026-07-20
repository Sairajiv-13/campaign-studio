"""Labeled A/B copy pairs with a human-preferred winner.

Each pair holds two variants for the same context and the variant a marketer would
actually send, with the reason. A good scorer ranks the preferred variant higher.
The winning side alternates between A and B so a position-biased baseline scores
only ~50%.

The set has two halves that measure different things:

* ``PAIRS`` (p01-p12) isolate one lever each — CTA, personalization,
  deliverability, brand voice, subject, clarity. The preferred variant is stronger
  on that lever and the other is weaker on exactly it. A working scorer sweeps
  these, which makes them a **regression test**.
* ``ADVERSARIAL_PAIRS`` (a01-a06) are cases where the preferred copy *loses* on a
  measured dimension. These are the actual benchmark; two of them currently fail,
  by design. See docs/EVALUATION.md for the failure analysis.
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

# --------------------------------------------------------------------------- #
# Adversarial pairs
# --------------------------------------------------------------------------- #
# The pairs above each isolate one lever the scorer explicitly measures, so a
# working scorer should sweep them — which makes them a regression test, not a
# hard benchmark. These are the opposite: cases where the copy a marketer would
# actually pick *loses* on at least one measured dimension. They are expected to
# expose real failure modes, and they do (see docs/EVALUATION.md). Keeping known
# failures in the set is deliberate: an eval you always pass tells you nothing.
ADVERSARIAL_PAIRS: list[EvalPair] = [
    EvalPair(
        "a01",
        "over_personalization",
        "email",
        "friendly",
        ["browsed running shoes"],
        "{first_name}, still thinking about those running shoes?",
        "Hi {first_name},\n\nWe saw you looking at running shoes at 11pm last night, and "
        "again this morning from your phone. Still deciding? Shop now →",
        "New arrivals in running",
        "Hi,\n\nOur new running range just landed. Take a look whenever you're ready.\n\nShop now →",
        "b",
        "A cites specific browsing times — maximally 'personalized' and maximally creepy. "
        "Relevance is not the same as surveillance, and the scorer has no notion of that.",
    ),
    EvalPair(
        "a02",
        "substance",
        "email",
        "friendly",
        ["cart abandoner"],
        "Your cart",
        "Buy now →",
        "Your cart is still here",
        "Hi {first_name},\n\nYour cart's saved for 48 hours. Free returns if it's not right.\n\nShop now →",
        "b",
        "A is maximally readable and has a strong CTA but says nothing. Short and punchy "
        "is not the same as persuasive; the readability score can't tell them apart.",
    ),
    EvalPair(
        "a03",
        "clickbait",
        "email",
        "playful",
        ["re-engagement"],
        "You won't believe what happened",
        "Hi {first_name},\n\nWe've been busy. Come see what changed.\n\nTake a look →",
        "Your account has 3 new features",
        "Hi {first_name},\n\nThree things launched since you were last here.\n\nTake a look →",
        "b",
        "A is clean, well-formed, spam-word-free — and pure clickbait. Specificity beats "
        "curiosity for lifecycle mail, but nothing in the rubric penalizes a vague hook.",
    ),
    EvalPair(
        "a04",
        "near_miss_banned",
        "email",
        "friendly",
        ["supplement buyer"],
        "The miracle formula everyone's talking about",
        "Hi {first_name},\n\nOur miracle formula is back in stock. Claim yours →",
        "Back in stock: your daily blend",
        "Hi {first_name},\n\nYour daily blend is back in stock. Claim yours →",
        "b",
        "Banned list says 'miracle cure'; A says 'miracle formula'. Substring matching "
        "misses the paraphrase, which is exactly how compliance problems get shipped.",
        ["miracle cure"],
    ),
    EvalPair(
        "a05",
        "emphasis_caps",
        "sms",
        "urgent",
        ["flash sale"],
        "",
        "{first_name}, FREE shipping ends tonight. Claim it: ex.co/go",
        "",
        "{first_name}, free shipping ends tonight. Claim it: ex.co/go",
        "a",
        "One capitalized word for emphasis is normal marketing copy, but the caps-ratio "
        "check treats short SMS as shouting. Small corpus, blunt heuristic.",
    ),
    EvalPair(
        "a06",
        "tone_subtlety",
        "email",
        "luxury",
        ["high lifetime value"],
        "An exclusive, curated selection, reserved for you",
        "{first_name}, we've crafted an exclusive, curated, elevated selection reserved "
        "exclusively for our most exclusive members. Explore now →",
        "Reserved for you",
        "{first_name}, a small selection we thought you'd appreciate. Explore now →",
        "b",
        "A stuffs every luxury lexicon word in and reads like a parody. The tone check "
        "rewards keyword presence, not restraint.",
    ),
]

PAIRS.extend(ADVERSARIAL_PAIRS)
