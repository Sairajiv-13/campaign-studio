"""The /metrics endpoint exposes the expected Prometheus series."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

_BRIEF = {
    "brief": {
        "product_name": "Aurora",
        "product_description": "sleep and focus supplements",
        "value_props": ["fall asleep faster"],
        "brand_voice": {"tone": "friendly", "banned_phrases": []},
        "goal": "abandoned_cart",
        "channels": ["email"],
        "segments": [
            {
                "id": "cart",
                "name": "Cart abandoners",
                "traits": ["added to cart"],
                "incentive": "10% off",
            }
        ],
        "variants_per_segment": 2,
    }
}


async def test_metrics_endpoint_exposes_expected_series(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Generate a campaign so the LLM and campaign counters have samples.
    created = await client.post("/v1/campaigns", json=_BRIEF, headers=auth_headers)
    assert created.status_code == 201

    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")

    body = resp.text
    assert "llm_calls_total" in body
    assert "llm_latency_seconds" in body
    assert "campaign_generations_total" in body
    # The task label is populated from the prompt's TASK: marker.
    assert 'task="generate"' in body
    assert 'task="judge"' in body
