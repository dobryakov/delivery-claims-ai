"""Graph nodes (specs §5.2).

LLM nodes (classify, extract, judge) use the structured-output helper with a
safe fallback. Deterministic nodes (enrich, review, finalize, short-circuits)
never call an LLM — code owns the facts (specs §2).

State stores primitives only (str enum values, plain dicts) so the checkpointer
can persist it across the interrupt in a version-stable way.
"""

from __future__ import annotations

from langgraph.types import interrupt
from langsmith.run_helpers import get_current_run_tree

from src.feedback import post_manager_feedback
from src.graph.state import ClaimState
from src.llm import Node, get_chat_model
from src.prompts import CLASSIFY_PROMPT, EXTRACT_PROMPT, JUDGE_PROMPT
from src.schemas import (
    Category,
    ClassifyResult,
    ExtractResult,
    JudgeResult,
    ProposedAction,
    Sentiment,
    Urgency,
    Verdict,
)
from src.structured import StructuredOutputError, invoke_structured
from src.tools import OrderNotFoundError, get_delivery_facts


def _current_trace_id() -> str | None:
    """Root run id of the active LangSmith trace, if tracing is on."""
    rt = get_current_run_tree()
    return str(rt.trace_id) if rt is not None else None


def classify_node(state: ClaimState) -> ClaimState:
    model = get_chat_model(Node.CLASSIFY)
    try:
        result = invoke_structured(
            model, ClassifyResult, CLASSIFY_PROMPT, state["raw_complaint"]
        )
    except StructuredOutputError:
        # Safe default: treat as out-of-scope rather than guessing.
        result = ClassifyResult(
            category=Category.OTHER,
            sentiment=Sentiment.NEUTRAL,
            urgency=Urgency.LOW,
        )
    return {
        "trace_id": _current_trace_id(),
        "category": result.category.value,
        "sentiment": result.sentiment.value,
        "urgency": result.urgency.value,
    }


def extract_node(state: ClaimState) -> ClaimState:
    model = get_chat_model(Node.EXTRACT)
    try:
        result = invoke_structured(
            model, ExtractResult, EXTRACT_PROMPT, state["raw_complaint"]
        )
    except StructuredOutputError:
        result = ExtractResult(order_id=None, claim_summary=state["raw_complaint"])
    return {"order_id": result.order_id, "claim_summary": result.claim_summary}


def enrich_node(state: ClaimState) -> ClaimState:
    """Deterministic DB lookup and fact computation (no LLM)."""
    order_id = state.get("order_id")
    if not order_id:
        return {"order_found": False, "order_facts": None}
    try:
        facts = get_delivery_facts(order_id)
        return {"order_found": True, "order_facts": facts.model_dump()}
    except OrderNotFoundError:
        return {"order_found": False, "order_facts": None}


def _facts_block(facts: dict) -> str:
    keys = [
        "order_id",
        "carrier",
        "status",
        "promised_date",
        "delivered_at",
        "run_date",
        "delay_days",
        "is_late",
        "reference_compensation",
    ]
    return "\n".join(f"{k}: {facts.get(k)}" for k in keys)


def judge_node(state: ClaimState) -> ClaimState:
    facts = state.get("order_facts")
    assert facts is not None, "judge_node requires order_facts"

    model = get_chat_model(Node.JUDGE)
    user_prompt = (
        f"Customer claim:\n{state.get('claim_summary', '')}\n\n"
        f"System-computed facts:\n{_facts_block(facts)}"
    )
    try:
        result = invoke_structured(model, JudgeResult, JUDGE_PROMPT, user_prompt)
    except StructuredOutputError:
        # Safe default: never fabricate a verdict on failure.
        result = JudgeResult(
            verdict=Verdict.INSUFFICIENT_DATA,
            reasoning="Judge failed to produce a valid structured verdict.",
            proposed_action=ProposedAction(
                kind="escalate", detail="Manual review required."
            ),
        )
    return {
        "verdict": result.verdict.value,
        "reasoning": result.reasoning,
        "proposed_action": result.proposed_action.model_dump(),
    }


# --- Deterministic short-circuit nodes ---------------------------------------


def route_other_node(state: ClaimState) -> ClaimState:
    """Complaint is not about delivery delay (out of scope, specs §5.2)."""
    return {
        "verdict": Verdict.INSUFFICIENT_DATA.value,
        "reasoning": "Complaint is not about a delivery delay; out of scope.",
        "proposed_action": ProposedAction(
            kind="reroute", detail="Route to the appropriate support queue."
        ).model_dump(),
    }


def insufficient_node(state: ClaimState) -> ClaimState:
    """No order id, or order not found -> insufficient data (no LLM)."""
    if not state.get("order_id"):
        reason = "No order id could be extracted from the complaint."
        detail = "Ask the customer to provide their order number."
    else:
        reason = f"Order {state['order_id']} was not found in the system."
        detail = "Verify the order number with the customer."
    return {
        "verdict": Verdict.INSUFFICIENT_DATA.value,
        "reasoning": reason,
        "proposed_action": ProposedAction(
            kind="request_info", detail=detail
        ).model_dump(),
    }


# --- Human-in-the-loop --------------------------------------------------------


def _review_card(state: ClaimState) -> dict:
    """Build the data shown to the manager (specs §9)."""
    return {
        "complaint": state.get("raw_complaint"),
        "category": state.get("category"),
        "urgency": state.get("urgency"),
        "order_id": state.get("order_id"),
        "facts": state.get("order_facts"),
        "model_verdict": state.get("verdict"),
        "model_reasoning": state.get("reasoning"),
        "proposed_action": state.get("proposed_action"),
    }


def review_node(state: ClaimState) -> ClaimState:
    """Pause for manager review (specs §5.2).

    Emits the review card via `interrupt` and suspends. On resume it receives the
    manager's decision dict:
        {"decision": "approve"|"edit"|"reject",
         "verdict": <optional override>,
         "action_kind": <optional>, "action_detail": <optional>,
         "comment": <optional>}
    """
    decision = interrupt(_review_card(state))

    kind = decision.get("decision", "approve")
    status = {"approve": "approved", "edit": "edited", "reject": "rejected"}.get(
        kind, "approved"
    )
    verdict_changed = kind == "edit" and bool(decision.get("verdict"))
    action_changed = kind == "edit" and bool(
        decision.get("action_kind") or decision.get("action_detail")
    )
    feedback = {
        "decision": kind,
        "comment": decision.get("comment"),
        "manager_verdict": decision.get("verdict"),
        "verdict_changed": verdict_changed,
        "action_changed": action_changed,
    }
    updates: ClaimState = {"review_status": status, "manager_feedback": feedback}

    if kind == "edit":
        if decision.get("verdict"):
            updates["verdict"] = Verdict(decision["verdict"]).value
        if decision.get("action_kind") or decision.get("action_detail"):
            current = state.get("proposed_action") or {}
            updates["proposed_action"] = {
                "kind": decision.get("action_kind") or current.get("kind", "compensation"),
                "detail": decision.get("action_detail") or current.get("detail", ""),
            }
    return updates


def finalize_node(state: ClaimState) -> ClaimState:
    """Record the final decision and emit manager feedback to LangSmith.

    The feedback lands on the original judged trace as ground truth (specs §8.2),
    building a labeled corpus of model-vs-manager decisions without extra labeling.
    """
    final = {
        "verdict": state.get("verdict"),
        "action": state.get("proposed_action"),
        "review_status": state.get("review_status"),
        "manager_feedback": state.get("manager_feedback"),
    }
    post_manager_feedback(state)
    return {"final_decision": final}
