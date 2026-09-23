"""Graph assembly (specs §5.1).

Stage 4: full workflow with human-in-the-loop.

    START -> classify -> [delivery_delay?] -> extract -> [order_id?]
          -> enrich -> [order found?] -> judge -> review (interrupt)
          -> [approved/edited?] -> finalize -> END

Off-ramps still set a verdict, then also go through review:
    classify (other)      -> route_other -> review
    extract (no order_id) -> insufficient -> review
    enrich  (not found)   -> insufficient -> review

Review outcomes:
    approve / edit -> finalize -> END
    reject         -> END (stop, flagged for manual handling; specs §2.3)
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.graph.nodes import (
    classify_node,
    enrich_node,
    extract_node,
    finalize_node,
    insufficient_node,
    judge_node,
    review_node,
    route_other_node,
)
from src.graph.state import ClaimState
from src.schemas import Category


def _after_classify(state: ClaimState) -> str:
    return (
        "extract"
        if state.get("category") == Category.DELIVERY_DELAY.value
        else "route_other"
    )


def _after_extract(state: ClaimState) -> str:
    return "enrich" if state.get("order_id") else "insufficient"


def _after_enrich(state: ClaimState) -> str:
    return "judge" if state.get("order_found") else "insufficient"


def _after_review(state: ClaimState) -> str:
    return "finalize" if state.get("review_status") in ("approved", "edited") else END


def build_graph(checkpointer=None):
    """Build and compile the claim workflow graph.

    A checkpointer is required for human-in-the-loop: it persists state across
    the interrupt so `submit` and `review` can run in separate processes.
    """
    graph = StateGraph(ClaimState)

    graph.add_node("classify", classify_node)
    graph.add_node("extract", extract_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("judge", judge_node)
    graph.add_node("route_other", route_other_node)
    graph.add_node("insufficient", insufficient_node)
    graph.add_node("review", review_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify", _after_classify, {"extract": "extract", "route_other": "route_other"}
    )
    graph.add_conditional_edges(
        "extract", _after_extract, {"enrich": "enrich", "insufficient": "insufficient"}
    )
    graph.add_conditional_edges(
        "enrich", _after_enrich, {"judge": "judge", "insufficient": "insufficient"}
    )

    # All verdict-setting nodes converge on manager review.
    graph.add_edge("judge", "review")
    graph.add_edge("route_other", "review")
    graph.add_edge("insufficient", "review")

    graph.add_conditional_edges(
        "review", _after_review, {"finalize": "finalize", END: END}
    )
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer)
