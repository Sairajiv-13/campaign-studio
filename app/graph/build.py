"""Assemble and run the campaign pipeline.

An explicit linear ``StateGraph``: generate -> score -> assemble. Compilation is
not free, so :class:`Pipeline` compiles once in its constructor and is built a
single time per process (see :mod:`app.deps`). This structure is the source of
truth for the Mermaid diagram in the README.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.domain.models import CampaignPlan
from app.graph import nodes
from app.graph.context import NodeContext
from app.graph.state import CampaignState

NODE_GENERATE = "generate"
NODE_SCORE = "score"
NODE_ASSEMBLE = "assemble"

NodeFn = Callable[[CampaignState, NodeContext], Awaitable[dict[str, Any]]]


def _bind(fn: NodeFn, ctx: NodeContext) -> Callable[[CampaignState], Awaitable[dict[str, Any]]]:
    async def run(state: CampaignState) -> dict[str, Any]:
        return await fn(state, ctx)

    return run


def build_graph(ctx: NodeContext) -> Any:
    builder: StateGraph = StateGraph(CampaignState)
    builder.add_node(NODE_GENERATE, _bind(nodes.generate_node, ctx))
    builder.add_node(NODE_SCORE, _bind(nodes.score_node, ctx))
    builder.add_node(NODE_ASSEMBLE, _bind(nodes.assemble_node, ctx))

    builder.add_edge(START, NODE_GENERATE)
    builder.add_edge(NODE_GENERATE, NODE_SCORE)
    builder.add_edge(NODE_SCORE, NODE_ASSEMBLE)
    builder.add_edge(NODE_ASSEMBLE, END)
    return builder.compile()


class Pipeline:
    """A compiled campaign pipeline. Compile once, run many times."""

    def __init__(self, ctx: NodeContext) -> None:
        self._graph = build_graph(ctx)

    async def run(self, state: CampaignState) -> CampaignPlan:
        result = await self._graph.ainvoke(state)
        final = CampaignState.model_validate(result)
        if final.plan is None:  # pragma: no cover - assemble always sets a plan
            raise RuntimeError("pipeline finished without producing a plan")
        return final.plan
