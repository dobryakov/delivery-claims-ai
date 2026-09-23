"""Evaluators for the golden-dataset run (specs §8.4).

Deterministic evaluators check exact matches against the reference. LLM-as-judge
evaluators (using MODEL_EVAL, a different family than the judge) assess grounding
and appropriateness — the meaningful core of evaluation under variant B.

Classic LangSmith evaluator signature: (run, example) -> dict with key/score.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from src.llm import Node, get_chat_model
from src.structured import StructuredOutputError, invoke_structured


# --- Deterministic evaluators -------------------------------------------------


def category_exact_match(run, example) -> dict:
    score = int(run.outputs.get("category") == example.outputs.get("category"))
    return {"key": "category_exact_match", "score": score}


def order_id_match(run, example) -> dict:
    score = int(run.outputs.get("order_id") == example.outputs.get("order_id"))
    return {"key": "order_id_match", "score": score}


def verdict_match(run, example) -> dict:
    score = int(run.outputs.get("verdict") == example.outputs.get("verdict"))
    return {"key": "verdict_match", "score": score}


# --- LLM-as-judge evaluators --------------------------------------------------


class EvalScore(BaseModel):
    score: int  # 1 = pass, 0 = fail
    comment: str


def _llm_eval(system_prompt: str, payload: dict, key: str) -> dict:
    model = get_chat_model(Node.EVAL)
    try:
        result = invoke_structured(
            model,
            EvalScore,
            system_prompt,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        return {"key": key, "score": int(bool(result.score)), "comment": result.comment}
    except StructuredOutputError as exc:
        return {"key": key, "score": 0, "comment": f"evaluator failed: {exc}"}


_GROUNDED_PROMPT = """\
You check whether a delivery-complaint verdict's reasoning is grounded ONLY in
the system-computed facts provided, without inventing dates, day counts, or
amounts. score=1 if fully grounded, score=0 if it introduces unsupported facts.
"""

_ACTION_PROMPT = """\
You check whether the proposed_action is appropriate for the verdict and facts,
per these guidelines: late delivery -> compensation by delay; on time -> decline;
in transit not due -> wait; overdue/lost -> escalate/refund. score=1 if
appropriate, score=0 otherwise.
"""

_DEVIATION_PROMPT = """\
The §6 guideline maps facts to an expected verdict (delivered & delay_days>0 ->
justified; delivered & delay_days<=0 -> not_justified; in_transit not due ->
insufficient_data; in_transit overdue or lost -> justified). If the model's
verdict matches the guideline, score=1. If it deviates, score=1 only when the
reasoning gives a sound, fact-based justification; otherwise score=0.
"""


def reasoning_grounded(run, example) -> dict:
    facts = run.outputs.get("facts")
    if not facts:  # deterministic path: fixed reasoning, trivially grounded
        return {"key": "reasoning_grounded", "score": 1, "comment": "no facts / n/a"}
    return _llm_eval(
        _GROUNDED_PROMPT,
        {"facts": facts, "reasoning": run.outputs.get("reasoning")},
        "reasoning_grounded",
    )


def action_appropriate(run, example) -> dict:
    facts = run.outputs.get("facts")
    if not facts:
        return {"key": "action_appropriate", "score": 1, "comment": "no facts / n/a"}
    return _llm_eval(
        _ACTION_PROMPT,
        {
            "facts": facts,
            "verdict": run.outputs.get("verdict"),
            "proposed_action": run.outputs.get("proposed_action"),
        },
        "action_appropriate",
    )


def deviation_justified(run, example) -> dict:
    facts = run.outputs.get("facts")
    if not facts:
        return {"key": "deviation_justified", "score": 1, "comment": "no facts / n/a"}
    return _llm_eval(
        _DEVIATION_PROMPT,
        {
            "facts": facts,
            "verdict": run.outputs.get("verdict"),
            "reasoning": run.outputs.get("reasoning"),
        },
        "deviation_justified",
    )


DETERMINISTIC_EVALUATORS = [category_exact_match, order_id_match, verdict_match]
LLM_EVALUATORS = [reasoning_grounded, action_appropriate, deviation_justified]
ALL_EVALUATORS = DETERMINISTIC_EVALUATORS + LLM_EVALUATORS
