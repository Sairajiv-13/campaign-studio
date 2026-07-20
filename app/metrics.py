"""Prometheus metrics.

Metric objects are process-global singletons (the Prometheus client model). Labels
are deliberately low-cardinality — the ``task`` label is the pipeline step
(``generate`` / ``judge``), never free text — so the series count stays bounded.
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

# Re-exported so callers don't import prometheus_client directly.
CONTENT_TYPE = CONTENT_TYPE_LATEST


def task_label(system: str) -> str:
    """Extract the pipeline step from a system prompt's ``TASK:`` marker."""

    match = _TASK_RE.search(system)
    return match.group(1).lower() if match else "unknown"


def render() -> bytes:
    return generate_latest()
