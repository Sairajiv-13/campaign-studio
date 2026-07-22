"""Cost surfaced on the plan + budget breaker, end to end (ADR-004)."""

from __future__ import annotations

import httpx
import pytest
from app.deps import Container

pytestmark = pytest.mark.integration

_BRIEF = {
    "brief": {
        "product_name": "Aurora",
        "product_description": "sleep and focus supplements",
        "value_props": ["fall asleep faster", "no grogginess"],
        "brand_voice": {"tone": "friendly"},
        "goal": "welcome",
        "channels": ["email"],
        "segments": [{"id": "new", "name": "New users", "traits": ["signed up"]}],
        "variants_per_segment": 3,
    }
}


async def test_plan_carries_cost_and_usage_endpoint_reports(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post("/v1/campaigns", json=_BRIEF, headers=auth_headers)
    assert resp.status_code == 201
    plan = resp.json()["plan"]
    # Sandbox is free, so the estimate is exactly 0.0, but the field is present
    # and wired, which is what proves the accounting path runs.
    assert plan["cost_usd"] == 0.0

    usage = await client.get("/v1/usage", headers=auth_headers)
    assert usage.status_code == 200
    body = usage.json()
    assert body["spent_today_usd"] == 0.0
    assert body["cap_usd"] > 0
    assert body["degraded"] is False


async def test_budget_cap_forces_sandbox(
    client: httpx.AsyncClient, auth_headers: dict[str, str], container: Container
) -> None:
    # Pretend we've already blown the daily budget on a real model.
    container.budget.add(container.settings.daily_budget_cap_usd + 1.0)
    assert container.budget.should_degrade()

    resp = await client.post("/v1/campaigns", json=_BRIEF, headers=auth_headers)
    assert resp.status_code == 201
    # The degraded pipeline is sandbox regardless of configured model.
    assert resp.json()["plan"]["model"] == "sandbox"

    usage = await client.get("/v1/usage", headers=auth_headers)
    assert usage.json()["degraded"] is True
