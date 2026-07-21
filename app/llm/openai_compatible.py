"""Real LLM adapter for any OpenAI-compatible endpoint (OpenAI, Ollama, vLLM...).

Defaults target a local Ollama server so the studio runs with no paid account.
Owns one pooled ``httpx.AsyncClient`` and maps transport/HTTP failures onto the
port's exception contract.

Transient failures (timeouts, 5xx, 429) are retried with exponential backoff;
permanent failures (4xx, malformed response) fail fast — retrying them only burns
latency and quota.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from app.cost import LlmUsage, estimate_cost, record
from app.llm.base import LlmPort, PermanentLlmError, TransientLlmError
from app.logging import get_logger
from app.metrics import LLM_CALLS, LLM_COST, LLM_LATENCY, task_label

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
# Delay after attempt 1 and attempt 2 respectively.
BACKOFF_SECONDS = (1.0, 2.0)


class OpenAICompatibleLlm(LlmPort):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    async def complete(
        self, *, system: str, user: str, json_mode: bool = False, temperature: float = 0.7
    ) -> str:
        payload: dict[str, object] = {
            "model": self._model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        task = task_label(system)
        started = time.perf_counter()
        status = "error"
        try:
            result = await self._complete_with_retry(payload)
            status = "ok"
            return result
        finally:
            LLM_CALLS.labels(task=task, status=status).inc()
            LLM_LATENCY.labels(task=task).observe(time.perf_counter() - started)

    async def _complete_with_retry(self, payload: dict[str, object]) -> str:
        last_error: TransientLlmError | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                return await self._call(payload)
            except TransientLlmError as exc:
                last_error = exc
                if attempt == MAX_ATTEMPTS - 1:
                    break
                delay = BACKOFF_SECONDS[attempt]
                logger.warning(
                    "llm_retry", extra={"attempt": attempt + 1, "delay": delay, "code": exc.code}
                )
                await asyncio.sleep(delay)

        assert last_error is not None  # loop only breaks after catching an error
        raise last_error

    async def _call(self, payload: dict[str, object]) -> str:
        try:
            response = await self._client.post("/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise TransientLlmError("LLM request timed out", code="llm_timeout") from exc
        except httpx.TransportError as exc:
            raise TransientLlmError("LLM transport error", code="llm_transport") from exc

        if response.status_code >= 500 or response.status_code == 429:
            raise TransientLlmError(f"LLM upstream error: {response.status_code}")
        if response.status_code >= 400:
            raise PermanentLlmError(
                f"LLM rejected request: {response.status_code} {response.text[:200]}"
            )

        try:
            data = response.json()
            content = str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise PermanentLlmError("Malformed LLM response") from exc

        # Record cost from the provider's usage block (ADR-004). Absent (some
        # OpenAI-compatible servers omit it) -> record zero tokens rather than guess.
        usage = data.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))
        cost = estimate_cost(self._model, tokens_in, tokens_out)
        record(
            LlmUsage(model=self._model, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost)
        )
        LLM_COST.labels(model=self._model).inc(cost)
        return content

    async def aclose(self) -> None:
        await self._client.aclose()
