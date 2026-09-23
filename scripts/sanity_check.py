"""Stage 0-1 sanity check.

Offline part (no API needed):
  * (re)build the orders database from the seed;
  * print computed delivery facts for the seed orders.

Online part (needs OPENROUTER_API_KEY, optional LangSmith):
  * issue one traced "hello" LLM call through OpenRouter so a trace shows up in
    LangSmith (specs §8.0). Skipped automatically if no key is configured.

Run:  uv run python -m scripts.sanity_check
"""

from __future__ import annotations

from src.config import get_settings
from src.db import init_db
from src.llm import Node, get_chat_model
from src.observability import enable_tracing
from src.tools import OrderNotFoundError, get_delivery_facts

SEED_ORDER_IDS = [
    "ORD-10432",  # delivered late
    "ORD-10510",  # delivered early
    "ORD-10788",  # in transit, not due
    "ORD-10801",  # in transit, overdue
    "ORD-10855",  # lost
    "ORD-10902",  # delivered on time
    "ORD-00000",  # not found
]


def check_database() -> None:
    print("== Rebuilding orders database from seed ==")
    init_db()
    settings = get_settings()
    print(f"Run date: {settings.run_date.isoformat()}\n")

    print("== Computed delivery facts ==")
    for order_id in SEED_ORDER_IDS:
        try:
            facts = get_delivery_facts(order_id)
        except OrderNotFoundError:
            print(f"  {order_id}: NOT FOUND")
            continue
        print(
            f"  {order_id}: status={facts.status}, "
            f"delay_days={facts.delay_days}, is_late={facts.is_late}, "
            f"comp={facts.reference_compensation!r}"
        )
    print()


def check_llm() -> None:
    settings = get_settings()
    if not settings.openrouter_api_key:
        print("== LLM hello trace: SKIPPED (no OPENROUTER_API_KEY) ==")
        return

    traced = enable_tracing(settings)
    print("== LLM hello trace ==")
    print(f"  Judge model: {settings.model_judge}")
    print(f"  LangSmith tracing: {'on -> ' + settings.langsmith_project if traced else 'off'}")

    model = get_chat_model(Node.JUDGE)
    response = model.invoke("Reply with exactly the word: pong")
    print(f"  Model replied: {response.content!r}\n")


def main() -> None:
    check_database()
    check_llm()
    print("Sanity check complete.")


if __name__ == "__main__":
    main()
