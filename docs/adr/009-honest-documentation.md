# 9. Document design rationale, not invented operational history

- Status: Accepted
- Date: 2026-07-21

## Context

It's tempting to present a portfolio project with a production history it doesn't
have: "generated N campaigns for a 40k-subscriber list," a dated incident, a real
provider bill, a Grafana screenshot full of traffic. Those make a project look
battle-tested. For a system that has not run at load, they're fabrications — and a
reviewer who checks (asks one follow-up, reads the commit history, notices there was
never a deployment) is right to distrust everything else once they find one.

This project made cost accounting, resilience, idempotency, guardrails, and
observability *real* in code. This ADR settles how to describe them.

## Decision

Every claim in these docs is one of three kinds, and labeled as such:

1. **Verifiable now** — runnable from this repo: the test suite, the scorer
   validation harness, the guardrail rules, `/metrics`, `/v1/usage`. Stated plainly.
2. **Design rationale** — why a mechanism exists and how it behaves. Stated as
   design intent, not as a war story ("the budget breaker degrades to sandbox at the
   cap," never "the day our bill hit $X").
3. **Unverified** — anything needing a real deployment, real traffic, or a real
   model at scale: labeled explicitly, with the reason.

Concretely, in this repo:

- Costs are **estimates at published per-token rates**, computed locally and
  process-local — never presented as a reconciled bill. `/v1/usage` says so in its
  own response payload.
- The Grafana dashboard ships as **JSON**, not a screenshot. Its panels are empty
  until something scrapes a live instance, and the docs say that.
- Real-model validation was **attempted and blocked by hardware**; the attempt and
  repro steps are recorded in [EVALUATION.md](../EVALUATION.md) rather than quietly
  replaced with sandbox numbers presented as model quality.
- The scorer's evaluation reports its **failure modes**, not just its wins — an
  adversarial set with documented misses beats a vanity 100%.

## Consequences

- A reviewer can trust the docs: every strong claim is either runnable or labeled.
  Nothing collapses under a follow-up question.
- Some numbers are less impressive than a fabricated version would be. That is the
  trade, made deliberately.
- New docs inherit the rule: if a number isn't reproducible from this repo, say so.
