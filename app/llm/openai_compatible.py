"""Real LLM adapter for any OpenAI-compatible endpoint (OpenAI, Ollama, vLLM...).

Defaults target a local Ollama server so the studio runs with no paid account.
Owns one pooled ``httpx.AsyncClient`` and maps transport/HTTP failures onto the
port's exception contract.
"""

from __future__ import annotations

import httpx

from app.llm.base import LlmPort, PermanentLlmError, TransientLlmError
from app.logging import get_logger

logger = get_logger(__name__)


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
            return str(response.json()["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise PermanentLlmError("Malformed LLM response") from exc

    async def aclose(self) -> None:
        await self._client.aclose()
