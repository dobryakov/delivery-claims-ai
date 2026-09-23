"""Graph state (specs §4).

A single TypedDict flows through all nodes; fields accumulate as the workflow
progresses. Stage 2 covers classify -> extract -> enrich -> judge (no HITL yet).
"""

from __future__ import annotations

from typing import TypedDict

# NOTE: fields are kept msgpack/JSON-safe (str enum values, plain dicts) so the
# checkpointer can persist and restore state across the interrupt in a
# version-stable way (specs §5.3). Enum values come from src.schemas.


class ClaimState(TypedDict, total=False):
    # Input
    raw_complaint: str

    # LangSmith trace of the submit run, so manager feedback can be attached to
    # the judged trace later (specs §8.1, §8.2).
    trace_id: str | None

    # classify (enum values as strings)
    category: str
    sentiment: str
    urgency: str

    # extract
    order_id: str | None
    claim_summary: str

    # enrich (DeliveryFacts serialized as a dict)
    order_facts: dict | None
    order_found: bool

    # judge
    verdict: str
    reasoning: str
    proposed_action: dict  # ProposedAction serialized as a dict

    # review (human-in-the-loop)
    review_status: str  # approved / edited / rejected
    manager_feedback: dict

    # finalize
    final_decision: dict
