"""LangSmith tracing setup (specs §8.0).

Propagates the resolved settings into the environment variables that langchain
and langsmith read. The project's LangSmith account is in the EU region, so the
endpoint must be set explicitly or ingestion returns 403.
"""

from __future__ import annotations

import os

from src.config import Settings, get_settings


def enable_tracing(settings: Settings | None = None) -> bool:
    """Turn on LangSmith tracing if configured. Returns True if active."""
    settings = settings or get_settings()
    if not settings.langsmith_tracing:
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    return bool(os.getenv("LANGSMITH_API_KEY"))
