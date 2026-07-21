# Observability

What the studio is doing, and what it's costing. Rationale in
[ADR-008](adr/008-observability.md); this is the how-to.

## Metrics catalog

Everything the app emits (`app/metrics.py`) and why:

| Metric | Type | What it answers |
|--------|------|-----------------|
| `llm_calls_total{task,status}` | counter | model call rate / error rate by step |
| `llm_latency_seconds{task}` | histogram | generate vs judge latency |
| `campaign_generations_total` | counter | how many campaigns generated |
| `llm_cost_usd_total{model}` | counter | **spend by model** |
| `campaign_cost_usd` | histogram | **cost per campaign** |
| `budget_cap_tripped_total` | counter | runs forced to sandbox by the cap |
| `campaign_cache_hits_total` | counter | repeat briefs served free (regens avoided) |
| `generation_fallbacks_total` | counter | slots that degraded to a template |
| `guardrail_flagged_variants_total{rule}` | counter | brand-safety flags by rule |

## Local Grafana

```bash
docker compose --profile observability up
```

- Grafana: <http://localhost:3000> (anonymous admin; dashboard auto-provisioned under "Campaign Studio")
- Prometheus: <http://localhost:9090>

> **Honest note:** the dashboard panels are empty until Prometheus has scraped a
> running instance under traffic. This repo has never run at load — the value here
> is a correct dashboard *definition* wired to the real metric names, not a
> screenshot of invented data.

## What to watch

- **Cost per campaign** and **spend by model** — the headline for a generation tool.
- **Budget cap trips** — if this is climbing, real generation is silently degrading
  to sandbox; raise the cap or investigate the load ([OPERATIONS.md](OPERATIONS.md)).
- **Guardrail flags by rule** — a spike in `banned_phrase` or `merge_tag` means the
  model is producing unsafe copy; the guardrail is catching it, but it's a signal.
- **Generation fallbacks** — the model is erroring or returning junk on some slots.

## No tracing (on purpose)

This is a single-process app with a short synchronous pipeline; the per-task latency
histogram already localizes slowness. Distributed tracing would be unearned
complexity here — see [ADR-008](adr/008-observability.md).
