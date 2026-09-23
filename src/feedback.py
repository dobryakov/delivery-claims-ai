"""Emit manager review outcomes to LangSmith as ground-truth feedback (§8.2).

Feedback is attached to the root run of the original submit trace (its
trace_id, captured during classify), so the manager's decision is recorded
against the trace that produced the judged verdict. This accumulates a labeled
model-vs-manager corpus for online monitoring (§8.5) and future datasets (§8.3).

Best-effort: any failure here is logged and swallowed so it never breaks the
finalize step.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from langsmith import Client

if TYPE_CHECKING:  # avoid import cycle at runtime
    from src.graph.state import ClaimState


def post_manager_feedback(state: "ClaimState") -> None:
    trace_id = state.get("trace_id")
    fb = state.get("manager_feedback")
    if not trace_id or not fb:
        return

    status = state.get("review_status")
    rejected = status == "rejected"
    verdict_correct = 0 if (rejected or fb.get("verdict_changed")) else 1
    action_correct = 0 if (rejected or fb.get("action_changed")) else 1
    comment = fb.get("comment") or ""

    try:
        client = Client()

        def send(key, *, score=None, value=None, comment=None):
            client.create_feedback(
                run_id=trace_id, key=key, score=score, value=value, comment=comment
            )

        # The run_id form emits a forward-compat deprecation notice; silence it
        # here since the feedback still attaches correctly to the trace.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Boolean-style scores: was the model's judgment accepted as-is?
            send("verdict_correct", score=verdict_correct)
            send("action_correct", score=action_correct)
            # Categorical ground truth: the manager's final verdict.
            send("manager_verdict", value=state.get("verdict"), comment=comment or None)
            # Bookkeeping: how the review was resolved.
            send("review_status", value=status)
    except Exception as exc:  # pragma: no cover - never break finalize
        print(f"[feedback] failed to post manager feedback: {exc}")
