-- Mock orders database schema and seed data (specs §3).
-- Deterministic fixtures so golden datasets and tests stay reproducible.

DROP TABLE IF EXISTS deliveries;
DROP TABLE IF EXISTS orders;

CREATE TABLE orders (
    order_id    TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    created_at  TEXT NOT NULL,   -- ISO-8601 datetime
    carrier     TEXT NOT NULL,
    sla_days    INTEGER NOT NULL
);

CREATE TABLE deliveries (
    order_id      TEXT NOT NULL REFERENCES orders(order_id),
    promised_date TEXT NOT NULL,   -- ISO-8601 date: date shown to the customer
    shipped_at    TEXT NOT NULL,   -- ISO-8601 datetime
    delivered_at  TEXT,            -- ISO-8601 datetime, NULL if not delivered yet
    status        TEXT NOT NULL CHECK (status IN ('delivered', 'in_transit', 'lost'))
);

-- Orders -----------------------------------------------------------------------
INSERT INTO orders (order_id, customer_id, created_at, carrier, sla_days) VALUES
    ('ORD-10432', 'CUST-001', '2026-09-05T10:12:00', 'FastPost', 5),
    ('ORD-10510', 'CUST-002', '2026-09-07T14:30:00', 'FastPost', 5),
    ('ORD-10788', 'CUST-003', '2026-09-10T09:00:00', 'CityExpress', 5),
    ('ORD-10801', 'CUST-004', '2026-09-11T18:45:00', 'CityExpress', 5),
    ('ORD-10855', 'CUST-005', '2026-09-12T08:20:00', 'FastPost', 5),
    ('ORD-10902', 'CUST-006', '2026-09-14T12:00:00', 'SlowMail', 7);

-- Deliveries -------------------------------------------------------------------
-- ORD-10432: delivered 4 days late  -> justified
INSERT INTO deliveries VALUES
    ('ORD-10432', '2026-09-10', '2026-09-06T08:00:00', '2026-09-14T16:20:00', 'delivered');

-- ORD-10510: delivered one day early -> not justified
INSERT INTO deliveries VALUES
    ('ORD-10510', '2026-09-12', '2026-09-08T08:00:00', '2026-09-11T11:05:00', 'delivered');

-- ORD-10788: still in transit, promised date not yet reached -> insufficient_data
INSERT INTO deliveries VALUES
    ('ORD-10788', '2026-09-30', '2026-09-11T08:00:00', NULL, 'in_transit');

-- ORD-10801: in transit but promised date already passed -> justified (escalate)
INSERT INTO deliveries VALUES
    ('ORD-10801', '2026-09-15', '2026-09-12T08:00:00', NULL, 'in_transit');

-- ORD-10855: lost -> justified (refund/reship)
INSERT INTO deliveries VALUES
    ('ORD-10855', '2026-09-16', '2026-09-13T08:00:00', NULL, 'lost');

-- ORD-10902: delivered exactly on the promised date -> borderline / not justified
INSERT INTO deliveries VALUES
    ('ORD-10902', '2026-09-21', '2026-09-15T08:00:00', '2026-09-21T19:40:00', 'delivered');
