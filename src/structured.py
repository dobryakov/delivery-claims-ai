"""Structured-output helper: JSON-mode + Pydantic validation + one retry.

We do not rely on ChatOpenAI.with_structured_output(): several cheap OpenRouter
models support it poorly (specs §12). Instead we ask the model for a JSON object,
parse it into the target Pydantic model, and retry once with the validation error
fed back. If the second attempt still fails, the caller decides on a safe default
(specs §2.3).
"""

from __future__ import annotations

import json
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """Raised when the model fails to produce valid JSON after the retry."""


def _schema_hint(schema: type[BaseModel]) -> str:
    return json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)


def _extract_json(text: str) -> str:
    """Strip common markdown code fences and surrounding prose."""
    text = text.strip()
    if text.startswith("```"):
        # Remove leading ```json / ``` and trailing ```
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    # Fall back to the outermost JSON object.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def invoke_structured(
    model: ChatOpenAI,
    schema: type[T],
    system_prompt: str,
    user_prompt: str,
) -> T:
    """Call `model` and return a validated instance of `schema`.

    Raises StructuredOutputError if validation fails twice.
    """
    system = (
        f"{system_prompt}\n\n"
        "Respond with a single JSON object and nothing else. "
        "It must conform to this JSON schema:\n"
        f"{_schema_hint(schema)}"
    )
    messages = [SystemMessage(content=system), HumanMessage(content=user_prompt)]

    last_error: Exception | None = None
    for attempt in range(2):
        raw = model.invoke(messages).content
        try:
            payload = json.loads(_extract_json(str(raw)))
            return schema.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            # Feed the error back for the single retry.
            messages.append(HumanMessage(content=str(raw)))
            messages.append(
                HumanMessage(
                    content=(
                        f"That was not valid. Error: {exc}. "
                        "Return only a corrected JSON object matching the schema."
                    )
                )
            )

    raise StructuredOutputError(
        f"Failed to produce valid {schema.__name__} after retry: {last_error}"
    )
