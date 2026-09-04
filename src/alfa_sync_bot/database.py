import sqlite3


MIGRATION_1 = """
BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_runs (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    is_complete_snapshot INTEGER NOT NULL DEFAULT 0 CHECK (is_complete_snapshot IN (0, 1)),
    error_code TEXT
);

CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    external_lesson_id TEXT NOT NULL,
    external_group_id TEXT,
    group_name TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    status TEXT NOT NULL CHECK (status IN ('planned', 'conducted', 'cancelled')),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    deleted_at TEXT,
    UNIQUE (source, external_lesson_id)
);

CREATE TABLE IF NOT EXISTS lesson_changes (
    id INTEGER PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id),
    import_run_id INTEGER NOT NULL REFERENCES import_runs(id),
    change_type TEXT NOT NULL CHECK (change_type IN ('new', 'changed', 'deleted')),
    changed_fields_json TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_deliveries (
    id INTEGER PRIMARY KEY,
    lesson_change_id INTEGER NOT NULL REFERENCES lesson_changes(id),
    channel TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    UNIQUE (lesson_change_id, channel)
);

CREATE TABLE IF NOT EXISTS pay_rules (
    id INTEGER PRIMARY KEY,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
    currency TEXT NOT NULL DEFAULT 'RUB',
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    UNIQUE (duration_minutes, effective_from)
);

CREATE TABLE IF NOT EXISTS payment_periods (
    id INTEGER PRIMARY KEY,
    week_start TEXT NOT NULL UNIQUE,
    week_end TEXT NOT NULL,
    expected_payout_date TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'expected', 'paid'))
);

CREATE TABLE IF NOT EXISTS income_accruals (
    id INTEGER PRIMARY KEY,
    lesson_id INTEGER NOT NULL UNIQUE REFERENCES lessons(id),
    pay_rule_id INTEGER REFERENCES pay_rules(id),
    payment_period_id INTEGER REFERENCES payment_periods(id),
    amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
    currency TEXT NOT NULL DEFAULT 'RUB',
    status TEXT NOT NULL CHECK (status IN ('planned', 'earned', 'paid')),
    earned_at TEXT,
    paid_at TEXT,
    rate_override_reason TEXT
);

CREATE VIEW IF NOT EXISTS finance_events AS
SELECT
    'income:' || income_accruals.id AS event_id,
    'income' AS event_type,
    'lesson' AS source_type,
    CAST(income_accruals.lesson_id AS TEXT) AS source_id,
    income_accruals.earned_at AS occurred_at,
    income_accruals.amount_minor,
    income_accruals.currency,
    income_accruals.status,
    payment_periods.week_start,
    payment_periods.week_end,
    payment_periods.expected_payout_date,
    income_accruals.paid_at
FROM income_accruals
LEFT JOIN payment_periods ON payment_periods.id = income_accruals.payment_period_id;

INSERT OR IGNORE INTO pay_rules
    (duration_minutes, amount_minor, currency, effective_from)
VALUES
    (30, 40000, 'RUB', '2026-01-01'),
    (60, 80000, 'RUB', '2026-01-01'),
    (90, 120000, 'RUB', '2026-01-01');

INSERT OR IGNORE INTO schema_migrations (version, applied_at)
VALUES (1, CURRENT_TIMESTAMP);

COMMIT;
"""


def apply_migrations(connection: sqlite3.Connection) -> None:
    connection.executescript(MIGRATION_1)
