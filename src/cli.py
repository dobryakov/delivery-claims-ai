"""Command-line entry point (specs §2.1).

Commands:
    submit  -- file a complaint; runs the graph up to the manager-review pause.
    review  -- resume a paused complaint with the manager's decision.
    demo    -- run built-in complaints end to end, auto-approving each.

Submit and review are two separate invocations, deliberately split in time. A
SqliteSaver checkpointer persists the graph state across the interrupt, so the
process may exit between them and resume later by thread_id.

Examples:
    uv run python -m src.cli submit --text "Order ORD-10432 arrived 4 days late!"
    uv run python -m src.cli review --thread <id> --decision approve
    uv run python -m src.cli review --thread <id> --decision edit \\
        --verdict not_justified --comment "SLA actually met"
    uv run python -m src.cli demo
"""

from __future__ import annotations

import argparse
import json
import uuid

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from src.config import CHECKPOINTS_DB_PATH, DATA_DIR
from src.graph import build_graph
from src.observability import enable_tracing

DEMO_COMPLAINTS = [
    "Order ORD-10432 was promised for the 10th but only arrived on the 14th. Not happy!",
    "Where is my package for order ORD-10788? It still hasn't shown up.",
    "Hi, order ORD-10855 never arrived at all.",
    "I want to change the color of the shirt I ordered.",
    "My delivery was late but I don't remember the order number.",
]


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _print_card(card: dict, thread_id: str) -> None:
    print("\n=== MANAGER REVIEW REQUIRED ===")
    print(f"thread_id: {thread_id}")
    print(json.dumps(card, indent=2, ensure_ascii=False))
    print("\nResume with:")
    print(f"  uv run python -m src.cli review --thread {thread_id} --decision approve")


def _print_final(final: dict) -> None:
    print("\n=== FINAL DECISION ===")
    print(json.dumps(final, indent=2, ensure_ascii=False))


def _interrupt_card(result: dict) -> dict | None:
    interrupts = result.get("__interrupt__")
    if interrupts:
        return interrupts[0].value
    return None


def cmd_submit(args: argparse.Namespace) -> None:
    thread_id = args.thread or uuid.uuid4().hex[:12]
    with SqliteSaver.from_conn_string(str(CHECKPOINTS_DB_PATH)) as cp:
        graph = build_graph(cp)
        result = graph.invoke({"raw_complaint": args.text}, _config(thread_id))
    card = _interrupt_card(result)
    if card is not None:
        _print_card(card, thread_id)
    else:
        _print_final(result.get("final_decision", result))


def cmd_review(args: argparse.Namespace) -> None:
    decision = {
        "decision": args.decision,
        "verdict": args.verdict,
        "action_kind": args.action_kind,
        "action_detail": args.action_detail,
        "comment": args.comment,
    }
    with SqliteSaver.from_conn_string(str(CHECKPOINTS_DB_PATH)) as cp:
        graph = build_graph(cp)
        result = graph.invoke(Command(resume=decision), _config(args.thread))
    final = result.get("final_decision")
    if final is not None:
        _print_final(final)
    else:
        print(f"\nComplaint {args.thread} rejected — flagged for manual handling.")


def cmd_demo(args: argparse.Namespace) -> None:
    with SqliteSaver.from_conn_string(str(CHECKPOINTS_DB_PATH)) as cp:
        graph = build_graph(cp)
        for text in DEMO_COMPLAINTS:
            thread_id = uuid.uuid4().hex[:12]
            print(f"\n--- Complaint: {text}")
            result = graph.invoke({"raw_complaint": text}, _config(thread_id))
            card = _interrupt_card(result)
            if card is not None:
                print(
                    f"  model verdict: {card['model_verdict']} "
                    f"-> auto-approving as manager"
                )
                result = graph.invoke(
                    Command(resume={"decision": "approve"}), _config(thread_id)
                )
            _print_final(result.get("final_decision", {}))


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    enable_tracing()

    parser = argparse.ArgumentParser(prog="delivery-claims-ai")
    sub = parser.add_subparsers(dest="command", required=True)

    p_submit = sub.add_parser("submit", help="File a complaint.")
    src = p_submit.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="Complaint text.")
    src.add_argument("--file", help="Path to a file with the complaint text.")
    p_submit.add_argument("--thread", help="Optional explicit thread id.")
    p_submit.set_defaults(func=cmd_submit)

    p_review = sub.add_parser("review", help="Resume with a manager decision.")
    p_review.add_argument("--thread", required=True)
    p_review.add_argument(
        "--decision", required=True, choices=["approve", "edit", "reject"]
    )
    p_review.add_argument("--verdict", help="Override verdict (with --decision edit).")
    p_review.add_argument("--action-kind", dest="action_kind")
    p_review.add_argument("--action-detail", dest="action_detail")
    p_review.add_argument("--comment")
    p_review.set_defaults(func=cmd_review)

    p_demo = sub.add_parser("demo", help="Run built-in complaints, auto-approving.")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    if getattr(args, "file", None):
        with open(args.file, encoding="utf-8") as fh:
            args.text = fh.read().strip()
    args.func(args)


if __name__ == "__main__":
    main()
