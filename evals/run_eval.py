"""Run the offline evaluation against the golden dataset (specs §8.4).

Syncs `claims_golden` into LangSmith (creating it on first run), then runs the
graph target over it with the deterministic and LLM-as-judge evaluators. Results
(per-example scores and aggregates) appear in LangSmith for regression tracking.

Requires a working LANGSMITH_API_KEY (EU endpoint) and OPENROUTER_API_KEY.

    RUN_DATE=2026-09-23 uv run python -m evals.run_eval
"""

from __future__ import annotations

import os

# Pin the run date the golden verdicts were derived against, unless overridden.
from evals.datasets import DATASET_RUN_DATE, GOLDEN_CASES

os.environ.setdefault("RUN_DATE", DATASET_RUN_DATE)

from langsmith import Client, evaluate  # noqa: E402

from evals.evaluators import ALL_EVALUATORS  # noqa: E402
from evals.target import run_graph_to_review  # noqa: E402
from src.db import init_db  # noqa: E402
from src.observability import enable_tracing  # noqa: E402

DATASET_NAME = "claims_golden"


def sync_dataset(client: Client) -> None:
    """Create the dataset with examples on first run; skip if it already exists."""
    if client.has_dataset(dataset_name=DATASET_NAME):
        print(f"Dataset '{DATASET_NAME}' already exists — reusing it.")
        return
    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description="Golden delivery-delay complaints (specs §8.3).",
    )
    client.create_examples(
        dataset_id=dataset.id,
        inputs=[{"complaint": c["complaint"]} for c in GOLDEN_CASES],
        outputs=[
            {
                "category": c["category"],
                "order_id": c["order_id"],
                "verdict": c["verdict"],
            }
            for c in GOLDEN_CASES
        ],
    )
    print(f"Created dataset '{DATASET_NAME}' with {len(GOLDEN_CASES)} examples.")


def main() -> None:
    if not enable_tracing():
        raise SystemExit("LangSmith is not configured (need LANGSMITH_* in .env).")
    init_db()  # ensure the mock DB matches the dataset's assumptions

    client = Client()
    sync_dataset(client)

    print("Running evaluation...")
    results = evaluate(
        run_graph_to_review,
        data=DATASET_NAME,
        evaluators=ALL_EVALUATORS,
        experiment_prefix="claims-golden",
        client=client,
    )
    print("\nEvaluation complete. See LangSmith for the experiment results.")
    try:
        print(results)
    except Exception:  # pragma: no cover - printing is best-effort
        pass


if __name__ == "__main__":
    main()
