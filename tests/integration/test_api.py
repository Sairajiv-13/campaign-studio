"""Integration tests for the campaign API."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

_BRIEF = {
    "brief": {
        "product_name": "Aurora",
        "product_description": "sleep and focus supplements",
        "value_props": ["fall asleep faster", "no grogginess"],
        "brand_voice": {"tone": "friendly", "banned_phrases": ["miracle cure"]},
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
        "variants_per_segment": 3,
    }
}


async def test_create_and_fetch_campaign(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post("/v1/campaigns", json=_BRIEF, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    plan = body["plan"]
    assert plan["model"] == "sandbox"
    assert len(plan["segment_plans"]) == 1
    winner = plan["segment_plans"][0]["winner"]
    assert 0.0 <= winner["score"]["composite"] <= 1.0
    assert winner["variant"]["body"]

    campaign_id = body["id"]
    fetched = await client.get(f"/v1/campaigns/{campaign_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == campaign_id


async def test_auth_flow(client: httpx.AsyncClient) -> None:
    ok = await client.post(
        "/v1/auth/token", json={"account_id": "marketer", "password": "test-password"}
    )
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    resp = await client.post(
        "/v1/campaigns", json=_BRIEF, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201


async def test_wrong_password_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.post("/v1/auth/token", json={"account_id": "marketer", "password": "nope"})
    assert resp.status_code == 401


async def test_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.post("/v1/campaigns", json=_BRIEF)
    assert resp.status_code == 401


async def test_missing_segments_rejected(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    bad = {"brief": {**_BRIEF["brief"], "segments": []}}
    resp = await client.post("/v1/campaigns", json=bad, headers=auth_headers)
    assert resp.status_code == 422


async def test_unknown_campaign_404(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/v1/campaigns/nope", headers=auth_headers)
    assert resp.status_code == 404


async def test_oversized_body_rejected(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    big = {"brief": {**_BRIEF["brief"], "product_description": "x" * 300_000}}
    resp = await client.post("/v1/campaigns", json=big, headers=auth_headers)
    assert resp.status_code == 413


async def test_health_and_ui(client: httpx.AsyncClient) -> None:
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ui = await client.get("/")
    assert ui.status_code == 200
    assert "Lifecycle Campaign Studio" in ui.text
    assert ui.headers["x-content-type-options"] == "nosniff"
