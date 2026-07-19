"""LLM port and typed exceptions.

The studio uses a single narrow port for two jobs: generating copy variants and
judging brand-voice adherence. Domain and pipeline code depend on this Protocol,
never on a vendor client. Adapters translate vendor failures into exactly one of
the two exception types so callers can make retry decisions without vendor
knowledge.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class LlmAdapterError(Exception):
    code: str = "llm_adapter_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class TransientLlmError(LlmAdapterError):
    """Retryable failure (timeout, upstream 5xx/429)."""

    code = "llm_transient"


class PermanentLlmError(LlmAdapterError):
    """Non-retryable failure (bad request, auth, malformed response)."""

    code = "llm_permanent"


@runtime_checkable
class LlmPort(Protocol):
    async def complete(
        self, *, system: str, user: str, json_mode: bool = False, temperature: float = 0.7
    ) -> str:
        """Return a single completion. When ``json_mode`` is set, the adapter asks
        the model for a JSON object (and real backends set response_format)."""
        ...
