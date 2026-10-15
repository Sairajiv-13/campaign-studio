# Contributing

Short version: branch from main, keep the change small, run the checks, open a PR.

## Prerequisites

- Python 3.11 or newer. CI runs 3.12, and the README quickstart uses 3.12.
- Docker, if you want to run the studio in a container instead of locally.

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env
make run
```

The defaults in `.env.example` are sandbox safe. The studio is at http://localhost:8000, signed in as `marketer` with the local dev password from the README. With Docker instead: `docker compose up --build`.

## Checks

Run these before you push.

- `make lint`: ruff check and format check over `app`, `tests`, `evals`
- `make type`: mypy in strict mode over `app` and `evals`
- `make test`: the full suite
- `make cov`: pytest with the coverage gate, 80 percent minimum on `app`
- `make eval`: the copy scorer checked against the labeled A/B pairs, minimum accuracy 0.8

The test suite is hermetic: sandbox model, in-memory store, no services, no secrets. Tests live in `tests/unit` and `tests/integration`.

If you change scoring in `app/scoring` or the prompts in `app/prompting.py`, `make eval` is not optional. A scoring change that drops ranking accuracy below the gate fails CI, and that is the point of the gate.

## Where things live

- `app/domain`: Brief, Segment, Variant, ScoreBreakdown, CampaignPlan
- `app/graph`: LangGraph nodes (generate, score, assemble) and the compiled pipeline
- `app/llm`: the LLM port, with real (OpenAI-compatible) and sandbox implementations
- `app/scoring`: deterministic heuristics and the composite scorer
- `app/security`: JWT, scopes, in-process rate limiting
- `app/web`: the demo UI
- `evals/`: the labeled A/B dataset and the ranking accuracy harness
- `docs/adr`: architecture decision records, 001 to 010. Read the ADR for an area before you change how it behaves.

## Branches and commits

- Branch names: short and plain, such as `fix/scorer-tie-break` or `feat/segment-export`.
- Commit subjects: short, imperative, one change per commit. Example: `Count brand-safety failures against the score`.
- Keep formatting-only changes in their own commit.

## Pull requests

- Fill in the PR template. Say what changed, the exact commands you ran, and the result.
- CI must pass: lint, type check, coverage gate, scorer eval gate, and the Docker build.
- If you change code in `app/`, note the coverage number from `make cov` in the PR.
- If you change scoring or prompts, paste the `make eval` accuracy in the PR.
