"""Brief-fingerprint idempotency: don't pay twice for the same brief (ADR-006)."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

_BRIEF = {
    "brief": {
        "product_name": "Aurora",
        "product_description": "sleep supplements",
        "value_props": ["fall asleep faster"],
        "brand_voice": {"tone": "friendly"},
        "goal": "welcome",
        "channels": ["email"],
        "segments": [{"id": "new", "name": "New", "traits": ["signed up"]}],
        "variants_per_segment": 2,
    }
}


async def test_identical_brief_returns_cached_plan(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    first = await client.post("/v1/campaigns", json=_BRIEF, headers=auth_headers)
    second = await client.post("/v1/campaigns", json=_BRIEF, headers=auth_headers)
    assert first.status_code == second.status_code == 201
    # Same brief -> same campaign id, not a freshly generated one.
    assert first.json()["id"] == second.json()["id"]


async def test_force_regenerates_a_new_plan(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    first = await client.post("/v1/campaigns", json=_BRIEF, headers=auth_headers)
    forced = await client.post("/v1/campaigns?force=true", json=_BRIEF, headers=auth_headers)
    assert first.json()["id"] != forced.json()["id"]


async def test_different_brief_is_not_deduped(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    first = await client.post("/v1/campaigns", json=_BRIEF, headers=auth_headers)
    changed = {"brief": {**_BRIEF["brief"], "product_name": "Different"}}
    second = await client.post("/v1/campaigns", json=changed, headers=auth_headers)
    assert first.json()["id"] != second.json()["id"]
