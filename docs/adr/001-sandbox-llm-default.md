# 1. Sandbox LLM is the default, not a mock

- Status: Accepted
- Date: 2026-07-20

## Context

The studio's core loop is "generate copy, then judge it". Both steps want a model.
If a model is mandatory, then cloning the repo requires an API key or a multi-GB
local download before anything runs, which kills the demo, makes CI depend on a
paid third party, and makes tests non-deterministic (the same prompt returns
different copy on every run, so nothing can be asserted).

## Decision

`LLM_MODE=sandbox` is the **default**. The sandbox implements the same `LlmPort`
protocol as the real adapter and is selected in the composition root
(`app/deps.py`), so no calling code knows the difference.

The sandbox is deliberately **not** a constant-returning stub. It reads a `TASK:`
marker from the system prompt and:

- for `generate`, produces varied, plausible marketing copy from angle/CTA/tone
  rotations, intentionally varying CTA strength and personalization across variants
  so the scorer produces a **meaningful ranking** rather than a tie;
- for `judge`, scores brand-voice adherence from a tone lexicon plus a hard
  banned-phrase check.

Output is deterministic: identical input yields identical output.

Switching to a real model is one env flag (`LLM_MODE=real` +
`LLM_BASE_URL`), pointing at any OpenAI-compatible endpoint including local Ollama.

## Consequences

- `docker compose up` yields a fully working studio with **no accounts, no keys**.
- CI is hermetic and fast; the whole suite runs with no network.
- Determinism is what makes the evaluation harness possible. The scorer's ranking
  accuracy is measurable and regression-gated because the inputs are stable.
- The tradeoff: sandbox copy is templated, so it demonstrates the *pipeline and
  scoring*, not real model quality. The real adapter exists and shares the prompts,
  so the seam is honest rather than a mock-shaped hole.
