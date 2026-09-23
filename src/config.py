"""Central configuration: environment variables, paths, model selection.

All settings are loaded from the .env file (see .env.example). Keeping them in
one place lets nodes and tools stay free of hardcoded values (see specs §2.2).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# Project layout ---------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ORDERS_DB_PATH = DATA_DIR / "orders.db"
CHECKPOINTS_DB_PATH = DATA_DIR / "checkpoints.db"

# Load .env once at import time.
load_dotenv(ROOT_DIR / ".env")


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings."""

    # OpenRouter (all LLM calls go through it; OpenAI-compatible endpoint).
    openrouter_api_key: str
    openrouter_base_url: str

    # Per-node model ids (see specs §2.2).
    model_classify: str
    model_extract: str
    model_judge: str
    model_eval: str

    # LangSmith (cloud SaaS, see specs §8.0).
    langsmith_tracing: bool
    langsmith_project: str
    langsmith_endpoint: str

    # Fixed "run date" for reproducible in_transit branches (specs §2.3).
    run_date: date

    @classmethod
    def load(cls) -> "Settings":
        run_date_raw = os.getenv("RUN_DATE", "").strip()
        run_date = date.fromisoformat(run_date_raw) if run_date_raw else date.today()

        return cls(
            openrouter_api_key=_require("OPENROUTER_API_KEY"),
            openrouter_base_url=os.getenv(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ),
            model_classify=os.getenv(
                "MODEL_CLASSIFY", "google/gemini-2.5-flash-lite"
            ),
            model_extract=os.getenv(
                "MODEL_EXTRACT", "google/gemini-2.5-flash-lite"
            ),
            model_judge=os.getenv("MODEL_JUDGE", "deepseek/deepseek-chat"),
            model_eval=os.getenv("MODEL_EVAL", "openai/gpt-4o-mini"),
            langsmith_tracing=os.getenv("LANGSMITH_TRACING", "").lower()
            in ("1", "true", "yes"),
            langsmith_project=os.getenv("LANGSMITH_PROJECT", "delivery-claims-ai"),
            langsmith_endpoint=os.getenv(
                "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"
            ),
            run_date=run_date,
        )


def get_settings() -> Settings:
    """Return freshly resolved settings (cheap; env is already loaded)."""
    return Settings.load()
