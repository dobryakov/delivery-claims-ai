"""Golden evaluation dataset (specs §8.3).

Each example pairs a complaint with the expected classification, order id, and
verdict. The expected verdicts assume the deterministic mock DB (data/seed.sql)
and a pinned RUN_DATE of 2026-09-23, so results are reproducible (specs §2.3).

Covers every §6 branch: delivered-late, delivered-early, delivered-on-time,
in_transit-not-due, in_transit-overdue, lost, order-not-found, no-order-id, and
out-of-scope.
"""

from __future__ import annotations

# Pin the run date these expected verdicts were derived against.
DATASET_RUN_DATE = "2026-09-23"

GOLDEN_CASES: list[dict] = [
    {
        "complaint": "Order ORD-10432 was promised for the 10th but only arrived on the 14th. Not happy!",
        "category": "delivery_delay",
        "order_id": "ORD-10432",
        "verdict": "justified",
    },
    {
        "complaint": "I feel like order ORD-10510 arrived late, can you check?",
        "category": "delivery_delay",
        "order_id": "ORD-10510",
        "verdict": "not_justified",  # actually delivered a day early
    },
    {
        "complaint": "Where is my package for order ORD-10788? It still hasn't shown up.",
        "category": "delivery_delay",
        "order_id": "ORD-10788",
        "verdict": "insufficient_data",  # in transit, promised date not reached
    },
    {
        "complaint": "Order ORD-10801 was due days ago and it's still not here!",
        "category": "delivery_delay",
        "order_id": "ORD-10801",
        "verdict": "justified",  # in transit, past promised date
    },
    {
        "complaint": "Hi, order ORD-10855 never arrived at all.",
        "category": "delivery_delay",
        "order_id": "ORD-10855",
        "verdict": "justified",  # lost
    },
    {
        "complaint": "Order ORD-10902 felt late to me even though I got it.",
        "category": "delivery_delay",
        "order_id": "ORD-10902",
        "verdict": "not_justified",  # delivered exactly on the promised date
    },
    {
        "complaint": "My order ORD-99999 was super late, I want a refund.",
        "category": "delivery_delay",
        "order_id": "ORD-99999",
        "verdict": "insufficient_data",  # order not found
    },
    {
        "complaint": "My delivery was really late but I can't find my order number.",
        "category": "delivery_delay",
        "order_id": None,
        "verdict": "insufficient_data",  # no order id
    },
    {
        "complaint": "I want to change the color of the shirt I ordered.",
        "category": "other",
        "order_id": None,
        "verdict": "insufficient_data",  # out of scope
    },
    {
        "complaint": "The product I received is defective and I'd like a replacement.",
        "category": "other",
        "order_id": None,
        "verdict": "insufficient_data",  # out of scope
    },
    {
        "complaint": "Absolutely unacceptable — ORD-10432 came four days after the promised date!",
        "category": "delivery_delay",
        "order_id": "ORD-10432",
        "verdict": "justified",  # same order, stronger tone
    },
    {
        "complaint": "Still waiting on ORD-10801, it was supposed to be here already.",
        "category": "delivery_delay",
        "order_id": "ORD-10801",
        "verdict": "justified",  # in transit, overdue
    },
]
