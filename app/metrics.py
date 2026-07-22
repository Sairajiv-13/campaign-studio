"""Prometheus metrics.

Metric objects are process-global singletons (the Prometheus client model). Labels
are deliberately low-cardinality. The ``task`` label is the pipeline step
(``generate`` / ``judge``), never free text, so the series count stays bounded.
"""

from __future__ import annotations

import re

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

_TASK_RE = re.compile(r"TASK:\s*(\w+)", re.IGNORECASE)

LLM_CALLS = Counter("llm_calls_total", "LLM completions attempted", ["task", "status"])
LLM_LATENCY = Histogram("llm_latency_seconds", "LLM completion latency", ["task"])
CAMPAIGN_GENERATIONS = Counter(
    "campaign_generations_total", "Campaigns generated and scored end to end"
)

# Cost accounting (ADR-004).
LLM_COST = Counter("llm_cost_usd_total", "LLM spend in USD by model", ["model"])
BUDGET_TRIPPED = Counter(
    "budget_cap_tripped_total", "Real-model generations forced to sandbox by the budget cap"
)
CAMPAIGN_COST = Histogram("campaign_cost_usd", "Estimated cost per generated campaign (USD)")

# Idempotency (ADR-006): briefs served from cache instead of regenerated.
CAMPAIGN_CACHE_HITS = Counter(
    "campaign_cache_hits_total", "Repeat briefs served from cache without regenerating"
)

# Generation resilience (ADR-005): slots that fell back to a template.
GENERATION_FALLBACKS = Counter(
    "generation_fallbacks_total", "Generation slots that degraded to a templated variant"
)

# Brand-safety guardrail (ADR-007): variants flagged by the output gate.
GUARDRAIL_FLAGS = Counter(
    "guardrail_flagged_variants_total", "Generated variants flagged by a guardrail rule", ["rule"]
)

# Re-exported so callers don't import prometheus_client directly.
CONTENT_TYPE = CONTENT_TYPE_LATEST


def task_label(system: str) -> str:
    """Extract the pipeline step from a system prompt's ``TASK:`` marker."""

    match = _TASK_RE.search(system)
    return match.group(1).lower() if match else "unknown"


def render() -> bytes:
    return generate_latest()
