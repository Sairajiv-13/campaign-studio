# Operations runbook

What someone running this service needs: how to see its state, and the handful of
interventions it actually supports. Every `/v1` endpoint needs a bearer token
(`POST /v1/auth/token`).

> These are the procedures the code supports today — not an aspirational runbook.
> Where a capability is missing, it says so.

## State at a glance

| Question | Where |
|----------|-------|
| Is the service up? | `GET /health` |
| What have we spent today, and are we degraded? | `GET /v1/usage` (scope `campaigns:read`) |
| Everything, for Prometheus | `GET /metrics` |
| A specific campaign + its plan | `GET /v1/campaigns/{id}` |
| Dashboards | `docker compose --profile observability up` → Grafana on :3000 |

## The signals that matter

| Metric | What it tells you |
|--------|-------------------|
| `llm_cost_usd_total{model}` | spend by model (estimate, published rates) |
| `campaign_cost_usd` | cost distribution per generated campaign |
| `budget_cap_tripped_total` | generations forced to sandbox by the cap |
| `campaign_cache_hits_total` | regenerations avoided by brief fingerprinting |
| `generation_fallbacks_total` | slots that degraded to a template |
| `guardrail_flagged_variants_total{rule}` | which brand-safety rule is firing |
| `llm_calls_total{task,status}` / `llm_latency_seconds` | model health by pipeline step |

## Common interventions

### Responding to a tripped budget cap
Symptom: `GET /v1/usage` shows `"degraded": true`, `budget_cap_tripped_total`
climbs, and real-model generations are being served by the sandbox instead.

1. Look at `GET /v1/usage` for today's estimated spend against `warn`/`cap`.
2. If spend is legitimate and the cap is too low, raise `DAILY_BUDGET_CAP_USD` and
   restart. If it isn't, find the source before lifting the cap — check
   `campaign_cost_usd` for outlier campaigns and `llm_calls_total` for a retry storm.
3. Remember the counter is **process-local and resets on restart** (ADR-004), so a
   restart clears the degraded state whether or not you fixed the cause.

### A rule is flagging too much (or nothing)
`guardrail_flagged_variants_total{rule}` tells you which rule fires. The rules and
their severities live in `app/guardrails.py`:

| Rule | Severity | Effect |
|------|----------|--------|
| `sms_length` | hard | drops the variant below clean ones |
| `merge_tag` | hard | unknown `{tag}` would render literally |
| `banned_phrase` | hard | brand/compliance violation |
| `subject_length` | soft | advisory only |
| `spam_trigger` | soft | advisory only |
| `all_caps` | soft | advisory only |

Banned phrases are **per-brief** (`brand_voice.banned_phrases`), so tightening brand
rules is a request-body change, not a deploy. Changing a *rule* (or its severity) is
a code change with a test — deliberately, so brand-safety can't drift silently.

### Forcing a regeneration
Identical briefs return the cached plan (ADR-006). To regenerate, change any field
in the brief — or restart the process, which clears the in-memory cache. There is
**no cache-invalidation endpoint**; with an in-memory store it would be a restart
with extra steps.

### Cost control levers
Generation cost scales with **segments × channels × variants_per_segment**, plus one
judge call per variant. The caps that bound it:

| Env var | Default | Effect |
|---------|---------|--------|
| `MAX_SEGMENTS` | 8 | rejects oversized briefs at the boundary |
| `MAX_VARIANTS_PER_SEGMENT` | 5 | caps variants per segment |
| `MAX_REQUEST_BYTES` | 262144 | body-size limit (413) |
| `DAILY_BUDGET_WARN_USD` | 15 | logs a warning |
| `DAILY_BUDGET_CAP_USD` | 25 | forces the sandbox model |
| `LLM_MODE` | `sandbox` | `real` to hit a live provider |

## Deploys

Single image, one process (`uvicorn app.main:app`); see
[DEPLOYMENT.md](DEPLOYMENT.md). Because state is in-memory (ADR-002), **a deploy
drops all campaigns, the brief cache, and the daily spend counter** — acceptable for
this project's scope, and the first thing to change if it ever needed to be durable.
There is no blue/green or canary automation; a deploy is an image swap.

## What this runbook deliberately doesn't have

No queue draining, no dead-letter replay, no worker scaling — the pipeline is
synchronous and in-process (ADR-003/005). Adding that machinery would be complexity
this system hasn't earned. If generation volume ever justified it, the honest first
step is a real store (ADR-002), then a queue — in that order.
