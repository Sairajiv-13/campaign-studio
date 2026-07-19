"""Shared test fixtures. Fully hermetic: sandbox model, in-memory store, no secrets."""

from __future__ import annotations

import os

os.environ.update(
    {
        "APP_ENV": "ci",
        "LLM_MODE": "sandbox",
        "JWT_SECRET": "test-secret-value-please-do-not-use-in-prod",
        "SERVICE_ACCOUNT_ID": "marketer",
        "SERVICE_ACCOUNT_PASSWORD": "test-password",
        "RATE_LIMIT_REQUESTS": "1000",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.deps import Container, build_container  # noqa: E402
from app.llm.sandbox import SandboxLlm  # noqa: E402
from app.main import create_app  # noqa: E402
from app.security.jwt import create_access_token  # noqa: E402


@pytest.fixture
def sandbox_llm() -> SandboxLlm:
    return SandboxLlm()


@pytest_asyncio.fixture
async def container() -> Container:
    get_settings.cache_clear()
    built = build_container(get_settings())
    try:
        yield built
    finally:
        await built.aclose()


@pytest_asyncio.fixture
async def client(container: Container) -> httpx.AsyncClient:
    app = create_app()
    app.state.container = container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    settings = get_settings()
    token = create_access_token(
        subject="marketer",
        scopes=["campaigns:write", "campaigns:read"],
        secret=settings.jwt_secret,
        issuer=settings.jwt_issuer,
        ttl_seconds=3600,
    )
    return {"Authorization": f"Bearer {token}"}
