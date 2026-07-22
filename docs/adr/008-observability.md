# 8. Observability: metrics and a dashboard

- Status: Accepted
- Date: 2026-07-21

## Context

The studio already emits Prometheus metrics at `/metrics`. As the system grew cost
accounting, a budget breaker, idempotency, resilience, and guardrails, each added a
signal worth watching. This ADR records the observability posture and ships a
dashboard so those signals are actually visible, without adding infrastructure the
system doesn't need.

## Decision

- **Metrics (always on).** `app/metrics.py` exposes the operational signals (LLM
  call rate/latency by task, campaigns generated) plus the business KPIs this
  project is actually about: **cost by model, cost per campaign, budget-cap trips,
  cache hits (regenerations avoided), generation fallbacks, and guardrail flags by
  rule.**
- **A dashboard built on those exact metric names** ships in
  `ops/grafana/dashboards/campaign-studio.json`, with Prometheus + Grafana behind a
  compose profile (`docker compose --profile observability up`) and an
  auto-provisioned datasource + dashboard.
- **Structured logs** carry the key events (`budget_cap_tripped`,
  `campaign_cache_hit`, `generation_failed`) for correlation.

## Why no distributed tracing here

The ops-agent sibling project wires OpenTelemetry because it spans two processes
(an API and a separate worker), "where is it slow across the boundary" is a real
question there. This studio is **one process** running a short, synchronous
three-node pipeline; the per-task latency histogram already answers "generate vs
judge, how long." Adding a tracing SDK and a collector would be complexity the
architecture doesn't earn. If the pipeline ever became distributed, tracing goes in
then. Behind the same kind of opt-in seam.

## Honest limitations

- **The dashboard is a definition, not a screenshot.** Its panels are empty until
  Prometheus scrapes a running instance under some traffic. This repo has never run
  at load. The value is a correct dashboard wired to the real metric names, not an
  image of invented data (cf. ADR-009 on honest documentation).
- **Metrics are per-process.** Consistent with the in-memory store and budget
  (ADR-002/004): across replicas each has its own counters until scraped and summed
  by Prometheus.

## Consequences

- One `/metrics` endpoint plus a ready-to-import dashboard cover day-to-day
  visibility, including the cost and safety KPIs that matter for a marketing tool.
- The dependency budget stays honest: nothing telemetry-related is required to run
  or test the studio.
