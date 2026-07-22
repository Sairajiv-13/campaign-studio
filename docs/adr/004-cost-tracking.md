# 4. Cost tracking and a budget breaker

- Status: Accepted
- Date: 2026-07-21

## Context

One brief fans out into (segments × channels × variants) generation calls plus a
brand-voice judge call per variant. Easily 20–40 model calls for a single
campaign. On a paid model that is real money per click of "Generate," and a
marketer's first question is "what did this cost?" A generation tool that can't
answer that, or that has no ceiling on a runaway loop, isn't production-credible.

## Decision

- **Per-call accounting.** Every LLM call records an `LlmUsage` row (model, tokens,
  cost) into a request-scoped ledger (a `ContextVar`, so it's correct under
  concurrency without threading a ledger through every node). The real adapter
  reads the provider's `usage` block; the sandbox records $0 with a token estimate
  so call volume still shows up.
- **Cost on the artifact.** The total is stamped onto `CampaignPlan.cost_usd` and
  exposed at `GET /v1/usage`, so cost-per-campaign is a first-class output.
- **Budget breaker.** A process-local `BudgetTracker` sums daily spend; once it hits
  `DAILY_BUDGET_CAP_USD`, generation switches to the free sandbox pipeline instead
  of billing more (`budget_cap_tripped_total` increments). A warn threshold logs
  earlier.

Prices are **published provider rates** (USD/1M tokens), labeled as estimates
everywhere they surface.

## Honest limitations

- **These are estimates, not a bill.** This app has no production deployment and no
  real spend to report; the numbers come from list prices, not an invoice. Said
  plainly in the API response (`"estimate at published rates"`) and the README.
- **The budget is in-memory and process-local.** It resets on restart and each
  replica counts separately. Consistent with the in-memory store (ADR-002). It
  stops a runaway loop inside one process; a multi-instance deploy would move the
  counter to a shared store. Documented, not hidden.
- **Token estimates for servers that omit `usage`.** Some OpenAI-compatible servers
  don't return a usage block; we record zero rather than guess, so cost can
  under-report against such a backend. Noted at the call site.

## Consequences

- "What did this campaign cost?" is answerable, and a runaway generation degrades to
  free instead of burning budget.
- The accounting is one seam (`app/cost.py`) mirrored across both adapters, matching
  the sandbox/real symmetry the rest of the codebase uses.
