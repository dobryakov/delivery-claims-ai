"""LLM client factory.

Every LLM call in the project goes through OpenRouter, which exposes an
OpenAI-compatible endpoint. We therefore reuse langchain-openai's ChatOpenAI,
pointing its base_url at OpenRouter (see specs §2.2). Model ids are resolved
per graph node from configuration, so a model can be swapped via .env without
touching the graph.
"""

from __future__ import annotations

from enum import Enum

from langchain_openai import ChatOpenAI

from src.config import Settings, get_settings


class Node(str, Enum):
    """Graph nodes that issue LLM calls, plus the offline evaluator."""

    CLASSIFY = "classify"
    EXTRACT = "extract"
    JUDGE = "judge"
    EVAL = "eval"


def _model_for(node: Node, settings: Settings) -> str:
    return {
        Node.CLASSIFY: settings.model_classify,
        Node.EXTRACT: settings.model_extract,
        Node.JUDGE: settings.model_judge,
        Node.EVAL: settings.model_eval,
    }[node]


def get_chat_model(
    node: Node,
    *,
    temperature: float = 0.0,
    settings: Settings | None = None,
) -> ChatOpenAI:
    """Build a ChatOpenAI client for a given node, wired to OpenRouter.

    Temperature defaults to 0.0 for reproducible classification/extraction and
    stable judging; callers may override it per node if needed.
    """
    settings = settings or get_settings()
    return ChatOpenAI(
        model=_model_for(node, settings),
        temperature=temperature,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
