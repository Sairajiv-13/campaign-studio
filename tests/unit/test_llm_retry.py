"""Retry behavior of the real LLM adapter.

Transient failures are retried with exponential backoff; permanent failures are
not retried at all. ``asyncio.sleep`` is patched so the test is instant.
"""

from __future__ import annotations

import httpx
import pytest
from app.llm import openai_compatible
from app.llm.base import PermanentLlmError, TransientLlmError
from app.llm.openai_compatible import MAX_ATTEMPTS, OpenAICompatibleLlm


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record backoff delays instead of actually sleeping."""

    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(openai_compatible.asyncio, "sleep", fake_sleep)
    return delays


def _llm(handler: httpx.MockTransport) -> OpenAICompatibleLlm:
    client = httpx.AsyncClient(transport=handler, base_url="http://llm/v1")
    return OpenAICompatibleLlm(
        base_url="http://llm/v1", api_key="k", model="m", timeout_seconds=5, client=client
    )


def _ok() -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})


async def test_retries_transient_then_succeeds(no_sleep: list[float]) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _ok() if calls["n"] == 3 else httpx.Response(500, text="boom")

    result = await _llm(httpx.MockTransport(handler)).complete(system="TASK: generate", user="u")

    assert result == "hi"
    assert calls["n"] == 3
    assert no_sleep == [1.0, 2.0]  # exponential backoff between attempts


async def test_gives_up_after_max_attempts(no_sleep: list[float]) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="down")

    with pytest.raises(TransientLlmError):
        await _llm(httpx.MockTransport(handler)).complete(system="TASK: judge", user="u")

    assert calls["n"] == MAX_ATTEMPTS
    assert no_sleep == [1.0, 2.0]


async def test_permanent_error_is_not_retried(no_sleep: list[float]) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, text="bad request")

    with pytest.raises(PermanentLlmError):
        await _llm(httpx.MockTransport(handler)).complete(system="TASK: generate", user="u")

    assert calls["n"] == 1
    assert no_sleep == []


async def test_timeout_is_retried(no_sleep: list[float]) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectTimeout("slow", request=request)
        return _ok()

    assert (
        await _llm(httpx.MockTransport(handler)).complete(system="TASK: generate", user="u") == "hi"
    )
    assert calls["n"] == 2
    assert no_sleep == [1.0]
