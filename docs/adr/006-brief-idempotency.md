# 6. Idempotent generation by brief fingerprint

- Status: Accepted
- Date: 2026-07-21

## Context

Generating a campaign costs real model calls (ADR-004). The same brief gets
submitted more than once in normal use: a double-clicked button, a client retry
after a timeout, or a marketer re-running an unchanged brief to "get the results
again." Regenerating from scratch each time bills for output the marketer already
has — and, because generation is non-deterministic on a real model, hands back
*different* copy, which is confusing when they expected the same campaign.

This system has no external side effects (it doesn't send anything), so idempotency
here isn't about avoiding duplicate deliveries — it's about **not paying twice**.

## Decision

Each brief gets a deterministic fingerprint (`sha256` of its canonical JSON plus
the model label). On `POST /v1/campaigns`, if a plan for that fingerprint already
exists in the store, return it instead of regenerating (`campaign_cache_hits_total`
increments). `?force=true` opts out for a deliberate fresh run.

The model label is part of the fingerprint on purpose: a plan generated on the
sandbox must not be served back once the deployment switches to a real model, since
the copy would differ. Degraded (budget-capped) runs save under the sandbox
fingerprint for the same reason.

## Honest limitations

- **The cache lives in the in-memory store (ADR-002).** It resets on restart and is
  per-replica — the same brief can regenerate after a deploy or on a different
  instance. Acceptable here (the cost of an occasional regen is small, and there's
  no correctness risk); a shared cache would be the move if this served real
  traffic across replicas.
- **Fingerprint equality is exact.** A trivially reworded brief is a different
  brief and regenerates — by design; "similar" briefs legitimately want fresh copy.

## Consequences

- Re-submitting an unchanged brief is free and returns the identical plan.
- `force=true` is the explicit escape hatch for wanting new variants.
- Ties directly to the cost story (ADR-004): the cheapest campaign is the one you
  don't regenerate.
