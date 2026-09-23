"""Tools that read the orders database and compute delivery facts.

These functions are the "code owns the truth" half of the design (specs §2):
they fetch rows and deterministically derive delay_days / is_late / status and
the reference compensation. The LLM judge later reasons over these facts but
never recomputes them (specs §5.2, §2.3).
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel

from src.config import ORDERS_DB_PATH, get_settings
from src.db import get_connection


class OrderNotFoundError(Exception):
    """Raised when no order matches the given id."""


class DeliveryFacts(BaseModel):
    """Deterministically computed facts passed to the judge node.

    Dates are ISO strings for stable serialization into the graph state and
    LangSmith traces.
    """

    order_id: str
    carrier: str
    status: str
    promised_date: str
    shipped_at: str
    delivered_at: str | None
    run_date: str
    # Derived (code-owned) values:
    delay_days: int | None  # delivered/overdue days vs promised; None if unknown
    is_late: bool
    reference_compensation: str


# Reference compensation ladder (specs §6). Kept here for stage 0-1; will move
# to a dedicated config module alongside the judge prompt.
def _reference_compensation(delay_days: int | None, status: str) -> str:
    if status == "lost":
        return "full refund or reshipment"
    if delay_days is None:
        return "none (insufficient data)"
    if delay_days <= 0:
        return "none (delivered on time)"
    if delay_days <= 2:
        return "apology"
    if delay_days <= 5:
        return "10% promo code"
    return "20% promo code + priority shipping"


def get_order(order_id: str, db_path: Path = ORDERS_DB_PATH) -> sqlite3.Row:
    """Return the orders row for `order_id` or raise OrderNotFoundError."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise OrderNotFoundError(order_id)
    return row


def _compute_delay_days(
    promised_date: str,
    delivered_at: str | None,
    status: str,
    run_date: date,
) -> tuple[int | None, bool]:
    """Derive (delay_days, is_late) from raw delivery fields.

    - delivered: delay = delivered date - promised date.
    - in_transit: measured against the run date (overdue if past promised date).
    - lost: treated as late, but delay magnitude is undefined (None).
    """
    promised = date.fromisoformat(promised_date)

    if status == "delivered" and delivered_at:
        delivered = datetime.fromisoformat(delivered_at).date()
        delay = (delivered - promised).days
        return delay, delay > 0

    if status == "in_transit":
        if run_date > promised:
            return (run_date - promised).days, True
        return None, False  # not yet due -> insufficient data downstream

    if status == "lost":
        return None, True

    return None, False


def get_delivery_facts(
    order_id: str, db_path: Path = ORDERS_DB_PATH
) -> DeliveryFacts:
    """Fetch delivery row for `order_id` and compute derived facts."""
    order = get_order(order_id, db_path=db_path)

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM deliveries WHERE order_id = ?", (order_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise OrderNotFoundError(order_id)

    run_date = get_settings().run_date
    delay_days, is_late = _compute_delay_days(
        promised_date=row["promised_date"],
        delivered_at=row["delivered_at"],
        status=row["status"],
        run_date=run_date,
    )

    return DeliveryFacts(
        order_id=order_id,
        carrier=order["carrier"],
        status=row["status"],
        promised_date=row["promised_date"],
        shipped_at=row["shipped_at"],
        delivered_at=row["delivered_at"],
        run_date=run_date.isoformat(),
        delay_days=delay_days,
        is_late=is_late,
        reference_compensation=_reference_compensation(delay_days, row["status"]),
    )
