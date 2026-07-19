"""Dependencies injected into pipeline nodes.

Nodes are pure with respect to state but still need the LLM. They receive it via
a ``NodeContext`` rather than importing a singleton, which keeps them unit-testable
with the sandbox model and no infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.llm.base import LlmPort


@dataclass(frozen=True)
class NodeContext:
    llm: LlmPort
    model_label: str = "sandbox"
