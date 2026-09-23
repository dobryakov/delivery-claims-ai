"""Pydantic schemas for structured LLM outputs, shared across nodes.

Keeping all node output schemas in one module (specs §2.3). Each LLM node
returns a strict JSON object validated against one of these models.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    DELIVERY_DELAY = "delivery_delay"
    OTHER = "other"


class Sentiment(str, Enum):
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Verdict(str, Enum):
    JUSTIFIED = "justified"
    NOT_JUSTIFIED = "not_justified"
    INSUFFICIENT_DATA = "insufficient_data"


class ClassifyResult(BaseModel):
    """Output of the classify node."""

    category: Category
    sentiment: Sentiment
    urgency: Urgency


class ExtractResult(BaseModel):
    """Output of the extract node."""

    order_id: str | None = Field(
        default=None,
        description="Order id in the form ORD-<number>, or null if absent.",
    )
    claim_summary: str = Field(
        description="One or two sentences summarizing the customer's claim."
    )


class ProposedAction(BaseModel):
    """Recommended resolution attached to a verdict."""

    kind: str = Field(
        description="Action type, e.g. compensation / refund / decline / escalate."
    )
    detail: str = Field(description="Concrete offer or reason, human-readable.")


class JudgeResult(BaseModel):
    """Output of the judge node (the LLM's factual judgment, specs §5.2)."""

    verdict: Verdict
    reasoning: str = Field(
        description="Argument grounded in the provided facts; explain any "
        "deviation from the §6 guidelines."
    )
    proposed_action: ProposedAction
