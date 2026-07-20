# 3. LangGraph state machine over hand-rolled async calls

- Status: Accepted
- Date: 2026-07-20

## Context

The campaign flow is three ordered steps: generate variants per segment, score
every variant, then rank and assemble a plan. That could just as easily be three
`await`s in a function. So why bring in LangGraph at all?

## Decision

The pipeline is an explicit `StateGraph` over a single typed `CampaignState`
(`app/graph/`). Each node is a pure `async (state, ctx) -> dict` function that
returns only the fields it changed; LangGraph merges the delta.

Compilation is not free, so `Pipeline` compiles the graph **once** in its
constructor and is built a single time per process in the composition root — not
per request.

The reasons this beats three inline `await`s:

- **Testability.** Each node is unit-tested in isolation against the sandbox model
  with a fake `NodeContext`, asserting on its returned delta. No mocking of
  framework internals.
- **Inspectable state.** One validated Pydantic object carries the whole run, so
  the state is serializable, debuggable, and directly renderable in API responses.
- **Explicit structure.** The graph is the single source of truth for the Mermaid
  diagram in the README, and adding a step (say, a compliance-check node) is a node
  plus an edge rather than surgery on a long function.
- **Room to grow.** Conditional edges and branching are already available if a
  future step needs to route (e.g. skip SMS for a segment) without restructuring.

## Consequences

- A dependency and a small amount of ceremony for what is currently a linear flow —
  accepted deliberately, and the compile-once design keeps the runtime cost at zero
  per request.
- We give up dynamic, model-chosen tool selection. That is fine: this process is
  fixed by design, and a free-form agent loop would be harder to test and to trust.
