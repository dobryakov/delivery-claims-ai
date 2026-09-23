"""Offline tests for deterministic delivery-fact computation (specs §6).

No API calls: these exercise the code-owned facts only. The orders DB is built
from the seed and RUN_DATE is pinned for reproducible in_transit branches.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")
os.environ["RUN_DATE"] = "2026-09-23"

from src.db import init_db  # noqa: E402
from src.tools import OrderNotFoundError, get_delivery_facts  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _db():
    init_db()


@pytest.mark.parametrize(
    "order_id,status,delay_days,is_late",
    [
        ("ORD-10432", "delivered", 4, True),  # late
        ("ORD-10510", "delivered", -1, False),  # early
        ("ORD-10788", "in_transit", None, False),  # not due yet
        ("ORD-10801", "in_transit", 8, True),  # overdue in transit
        ("ORD-10855", "lost", None, True),  # lost
        ("ORD-10902", "delivered", 0, False),  # exactly on time
    ],
)
def test_delivery_facts(order_id, status, delay_days, is_late):
    facts = get_delivery_facts(order_id)
    assert facts.status == status
    assert facts.delay_days == delay_days
    assert facts.is_late == is_late


def test_order_not_found():
    with pytest.raises(OrderNotFoundError):
        get_delivery_facts("ORD-00000")


def test_reference_compensation_ladder():
    assert get_delivery_facts("ORD-10432").reference_compensation == "10% promo code"
    assert (
        get_delivery_facts("ORD-10855").reference_compensation
        == "full refund or reshipment"
    )
    assert "none" in get_delivery_facts("ORD-10510").reference_compensation
