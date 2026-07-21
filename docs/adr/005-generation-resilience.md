# 5. Generation resilience without a queue

- Status: Accepted
- Date: 2026-07-21

## Context

A campaign is dozens of independent model calls. Two things can go wrong: a single
completion comes back malformed or the model errors on one slot, and — separately —
the whole request is heavy. A production-credible tool has to survive the first
without a half-empty campaign, and has to be honest about the second.

The reflex from a backend background is "add a queue and a worker with retries and a
dead-letter." That would be the wrong move *here*, and saying why is the point of
this ADR.

## Decision

**Resilience is per-slot degradation, reported honestly — not a job queue.**

- Each (segment × channel) generation is independent. If the model errors or returns
  unparseable output, that one slot falls back to a templated variant
  (`_fallback_variant`) instead of failing the request. The LLM adapter already
  retries transient errors with backoff before it gets here.
- The pipeline **counts** fallbacks and stamps `CampaignPlan.fallback_count` +
  `degraded`, and increments `generation_fallbacks_total`. A degraded campaign is
  usable but flagged, so the marketer knows some slots are templated — silent
  degradation would be worse than the failure.

## Why no queue / worker / dead-letter

- **The work is synchronous and bounded.** A brief is capped
  (`MAX_SEGMENTS`, `MAX_VARIANTS_PER_SEGMENT`), so a request is tens of calls with a
  known ceiling, not an open-ended stream. There is no backlog to absorb.
- **There are no external side effects to make durable.** The studio *generates*
  copy; it does not send email or SMS. Nothing here needs at-least-once delivery or
  idempotent replay, so a dead-letter queue would guard against a class of failure
  that doesn't exist in this system.
- Adding a queue, a worker process, Redis, a reaper, and their tests would be
  infrastructure that demonstrates nothing this design needs — exactly the
  complexity this project declines to add (cf. ADR-002 on the store).

If the studio ever grows an *action* (actually scheduling/sending a campaign), that
new capability earns a durable queue — and it goes behind a port, like everything
else. Until then, this is the right amount of machine.

## Consequences

- One bad completion costs one templated slot, not the campaign.
- The plan tells the truth about its own quality (`degraded`, `fallback_count`).
- The "why no queue" reasoning is written down, so its absence reads as a decision,
  not an omission.
