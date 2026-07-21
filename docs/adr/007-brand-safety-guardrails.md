# 7. Brand-safety and compliance guardrails on generated copy

- Status: Accepted
- Date: 2026-07-21

## Context

The whole point of this tool is that an LLM writes copy that goes to real
customers, through real email/SMS infrastructure. That makes the generated text the
highest-risk output in the system: an SMS over the carrier limit gets split or
truncated, a broken `{merge_tag}` ships an unrendered literal to someone's inbox, a
banned/off-brand phrase is a compliance incident, and spam-trigger language quietly
destroys deliverability. The scorer already judges *quality* (tone, clarity, CTA).
It does not gate *safety* — "this is good copy" and "this is safe to send" are
different questions.

## Decision

Add a deterministic guardrail (`app/guardrails.py`) that runs on every generated
variant during scoring and attaches structured `GuardrailFlag`s:

| Rule | Severity | Why |
|------|----------|-----|
| `sms_length` | hard | SMS past 160 chars is split (cost) or truncated |
| `merge_tag` | hard | unknown/typo'd tag renders literally to the customer |
| `banned_phrase` | hard | brand/compliance-forbidden language |
| `subject_length` | soft | email subject likely truncated in the inbox |
| `spam_trigger` | soft | classic phrases that hurt deliverability |
| `all_caps` | soft | shouting reads as spam |

**A hard flag drops a variant below clean ones in ranking** — assemble sorts on
`(no hard flag, composite)`, so a brand-safety violation can't win a segment even
with a great score. Soft flags are advisory. Flags surface on each `ScoredVariant`,
increment `guardrail_flagged_variants_total{rule}`, and are gated in CI by a
poisoned-copy catch-rate (`evals/guardrails.py`, `--min-guardrail`, default 1.0).

## Why rules, not an LLM judge

For the failures that actually cause harm here — length, tags, banned phrases —
a regex is stricter, deterministic, free, and auditable, and (unlike a second
model) can't itself be prompt-injected by the copy it's checking. We deliberately
**don't** judge tone or truthfulness with a rule; the brand-voice *score* covers
tone, and "is this claim true" is out of scope for a linter.

## Honest limitations

- **It's a denylist, not a safety proof.** Fluent, plausible, non-triggering but
  factually wrong copy passes — no rule catches that, and we don't pretend it does.
- **The merge-tag allowlist and spam lexicon are illustrative**, not a real ESP's.
  A production deployment would source them from the send platform; the mechanism is
  the point.
- **Hard-flagged variants are ranked down, not deleted** — they still appear in the
  segment's list (transparency), just never as the winner.

## Consequences

- Unsafe copy can't win a segment; the marketer sees *why* via per-variant flags.
- A weakened rule fails a fast unit test and the eval gate, not a customer send.
- Consistent with the sandbox/cost seams: one deterministic gate over model output.
