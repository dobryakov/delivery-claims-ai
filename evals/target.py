"""Evaluation target: run the graph and read the model's pre-review output.

The judge's verdict is what we evaluate (specs §8.4), so we run the workflow up
to the manager-review interrupt and read the accumulated state — never resuming
into the human-in-the-loop step. An in-memory checkpointer is enough here.
"""

from __future__ import annotations

import uuid

from langgraph.checkpoint.memory import MemorySaver

from src.graph import build_graph


def run_graph_to_review(inputs: dict) -> dict:
    """LangSmith target function: returns the model's outputs for one complaint."""
    graph = build_graph(MemorySaver())
    thread_id = uuid.uuid4().hex[:12]
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke({"raw_complaint": inputs["complaint"]}, config)
    state = graph.get_state(config).values

    return {
        "category": state.get("category"),
        "order_id": state.get("order_id"),
        "verdict": state.get("verdict"),
        "reasoning": state.get("reasoning"),
        "proposed_action": state.get("proposed_action"),
        "facts": state.get("order_facts"),
    }
