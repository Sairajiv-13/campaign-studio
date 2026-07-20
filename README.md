<!-- GitHub topics: fastapi, langgraph, marketing-automation, llm, campaign-generation, python, prometheus, jwt, evaluation -->

# Lifecycle Campaign Studio

[![CI](https://github.com/sairajeev-collab/campaign-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/sairajeev-collab/campaign-studio/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Generates email/SMS campaign variants per audience segment, scores each one, and
> tells you which to send — with the scoring measured against human judgment, not
> assumed.

I wanted to see how far you can get grading marketing copy automatically. Writing
the copy is the easy half — any model will hand you five subject lines. Picking
which one actually goes out is the part most "AI marketing" demos skip, usually by
asking the model to grade its own homework.

So the generation here is deliberately unremarkable. The scoring is the point.

Give it a product brief and some segments, and it writes variants for each segment,
scores every one on brand voice, clarity, CTA strength, personalization, and
deliverability, then ranks them and hands back a winner plus a runner-up for A/B.

It runs with no API key and no model download — the generator and the brand-voice
judge both have deterministic sandbox implementations, so CI is hermetic and the
demo works offline. Point it at a real model with one env var when you want to.

**Run it:** `docker compose up --build` → http://localhost:8000 → sign in with
`marketer` / `local-dev-password`

---

## What makes it more than "call an LLM"

Generation is the boring half. The real question is which variant ships, and
"ask the model which one it likes" is circular — same student grading the exam.

So most of the scorer is plain Python:

| Dimension | How it's measured |
|-----------|-------------------|
| **brand_voice** | LLM-as-judge against the brand tone, plus a hard banned-phrase check in code |
| **clarity** | Flesch reading ease, plus subject-line length rules for email |
| **cta_strength** | strong vs weak call-to-action detection |
| **personalization** | merge tags, segment-trait references, second person |
| **deliverability** | spam triggers, shouting caps, exclamation abuse |

Those roll into a weighted composite. Brand voice and CTA carry the most weight;
deliverability is a floor you shouldn't sink through — great copy in the spam
folder is worth nothing.

I do use an LLM as the judge for brand voice, because tone is genuinely hard to
pin down with rules. But I don't trust it on its own. Banned phrases are checked
in code, not by the model, and if the judge is unreachable the score falls back to
that check instead of failing the request.

The obvious follow-up is "how do you know the scorer is any good?" So there's an
eval: 18 hand-labeled A/B pairs where the label is the variant a marketer would
actually send. The winning side alternates, so a positionally-biased scorer scores
~50% instead of looking accidentally good. `make eval` reports pairwise ranking
accuracy and CI fails below the threshold.

**It scores 88.9% — 16 of 18.** The two it misses are in the set on purpose.

Twelve of the pairs each isolate one lever the scorer measures, so it sweeps them;
that's a regression test, not a benchmark. The other six are adversarial: the copy
a marketer would pick *loses* on a measured dimension. Two of those break it:

- It prefers copy that cites your exact browsing times over a clean alternative.
  Maximum personalization score, maximum creepiness — the heuristic counts signals
  and has no concept of *appropriate*.
- It can't tell "You won't believe what happened" from "Your account has 3 new
  features". Both are well-formed; only one says anything. The rubric measures the
  shape of copy, not whether it has content.

Both are pinned by a test, so if either starts passing I'll know the scorer
actually improved instead of finding out by accident. Full write-up, including a
pass that succeeds for the wrong reason, is in [docs/EVALUATION.md](docs/EVALUATION.md).

Eighteen pairs labeled by one person isn't proof the scorer is right. It's enough
to catch a regression and to know two specific things it gets wrong.

## Architecture

```mermaid
flowchart LR
    ui[Demo UI /] -->|JWT| api[FastAPI]
    caller[API caller] -->|JWT| api
    api --> pipe[LangGraph pipeline]
    pipe --> gen[generate]
    gen --> score[score]
    score --> asm[assemble]
    gen -. copy .-> llm[[LLM port]]
    score -. brand-voice judge .-> llm
    score --> heur[[deterministic heuristics]]
    llm -.real.-> ollama[Ollama / OpenAI-compatible]
    llm -.sandbox.-> det[deterministic generator + judge]
```

## Pipeline

```mermaid
stateDiagram-v2
    [*] --> generate
    generate --> score
    score --> assemble
    assemble --> [*]
```

- **generate** — for each segment × channel, ask the model for N on-brand variants
  as JSON. A malformed completion falls back to a templated variant, so one bad
  response doesn't sink the whole campaign.
- **score** — grade every variant with the heuristics plus the brand-voice judge
  into a `ScoreBreakdown`.
- **assemble** — rank per segment, pick the winner and runner-up, roll up into a
  `CampaignPlan`.

Each node is a pure `async (state, ctx) -> dict` that returns only what it changed,
so they're unit-tested in isolation against the sandbox model. Design notes are in
[docs/adr/](docs/adr/).

## Quickstart

```bash
cp .env.example .env                 # defaults are sandbox-safe, no secrets
docker compose up --build            # studio on http://localhost:8000
```

Open `http://localhost:8000/`, sign in with `marketer` / `local-dev-password`,
pick segments, generate. Without Docker:

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"   # or plain pip
make run          # http://localhost:8000
```

### API

```bash
TOKEN=$(curl -s -X POST localhost:8000/v1/auth/token -H 'Content-Type: application/json' \
  -d '{"account_id":"marketer","password":"local-dev-password"}' | jq -r .access_token)

curl -s -X POST localhost:8000/v1/campaigns -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{
    "brief": {
      "product_name": "Aurora",
      "product_description": "sleep and focus supplements",
      "value_props": ["fall asleep faster", "no grogginess"],
      "brand_voice": {"tone": "friendly", "banned_phrases": ["miracle cure"]},
      "goal": "abandoned_cart",
      "channels": ["email", "sms"],
      "segments": [
        {"id": "cart", "name": "Cart abandoners", "traits": ["added to cart"], "incentive": "10% off"}
      ],
      "variants_per_segment": 3
    }
  }'
```

| Method & path | Auth | Purpose |
|---------------|------|---------|
| `GET /` | public | Demo UI |
| `GET /health` | public | Liveness + model + campaign count |
| `GET /metrics` | public | Prometheus metrics (LLM calls, latency, generations) |
| `POST /v1/auth/token` | service creds | Exchange credentials for a JWT |
| `POST /v1/campaigns` | `campaigns:write` | Generate + score a campaign |
| `GET /v1/campaigns/{id}` | `campaigns:read` | Fetch a stored plan |

## Using a real model

Set `LLM_MODE=real` and point `LLM_BASE_URL` at any OpenAI-compatible endpoint
(local Ollama by default — `ollama pull llama3.1`). Same code path: the prompts
already ask for JSON via `response_format`. Transient failures (timeouts, 5xx,
429) retry three times with 1s/2s backoff; 4xx and malformed responses fail fast,
since retrying those just burns quota.

The sandbox exists so the repo runs with nothing installed, not because the real
path is an afterthought.

## Evaluation

```bash
make eval        # python -m evals --min-accuracy 0.8
```

Reports pairwise ranking accuracy against the labeled pairs, broken down by lever,
and exits non-zero below the threshold so CI catches a scoring regression.

## Testing

Hermetic — sandbox model, in-memory store, no services, no secrets.

```bash
make test        # or: make cov  (>80% gate)
make lint type   # ruff + mypy strict
```

## Project layout

```
app/
  domain/     Brief, Segment, Variant, ScoreBreakdown, CampaignPlan
  llm/        LLM port + real (OpenAI-compatible) and sandbox generator/judge
  scoring/    deterministic heuristics + composite scorer (LLM-as-judge)
  graph/      LangGraph nodes (generate, score, assemble) + compiled pipeline
  security/   JWT, scopes, in-process rate limiting
  api/        FastAPI routes + schemas
  web/        self-contained demo UI
evals/        labeled A/B dataset + ranking-accuracy harness (CI gate)
docs/         ADRs, deployment guide, screenshots
tests/        unit + integration (hermetic)
```

Deployment notes and the full env var table are in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## What I'd do next

Roughly in the order I'd actually pick them up:

1. **Predicted engagement model** — the biggest gap. Right now engagement is a
   heuristic proxy; a small model trained on historical open/click data per segment
   would replace guesswork with evidence.
2. **Send-time optimization** — picking when to send, and which channel, per
   segment. Cheap to add, measurable lift.
3. **Multivariate testing** — real experiment tracking so the A/B winner is
   validated against actual results instead of just the scorer's opinion.
4. **Persistence and history** — swap the in-memory store for Postgres behind the
   existing interface, plus per-brand voice profiles.
5. **Guardrails** — claims and compliance checks for regulated copy (health,
   finance), beyond the banned-phrase list.
6. **Streaming generation** — mostly a UX win; the wait is noticeable with a real
   model.

---

Built by [Sairajeev](https://github.com/sairajeev-collab). MIT licensed.
