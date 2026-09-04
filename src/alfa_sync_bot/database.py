import sqlite3
from pathlib import Path
import os
import tempfile
from collections.abc import Callable


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

MIGRATION_2 = """
BEGIN;

CREATE TABLE IF NOT EXISTS runtime_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_migrations (version, applied_at)
VALUES (2, CURRENT_TIMESTAMP);

COMMIT;
"""


def apply_migrations(connection: sqlite3.Connection) -> None:
    connection.executescript(MIGRATION_1)
    connection.executescript(MIGRATION_2)


def get_runtime_state(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute(
        "SELECT value FROM runtime_state WHERE key = ?", (key,)
    ).fetchone()
    return None if row is None else row[0]


def set_runtime_state(
    connection: sqlite3.Connection, key: str, value: str
) -> None:
    connection.execute(
        "INSERT INTO runtime_state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET "
        "value = excluded.value, updated_at = CURRENT_TIMESTAMP",
        (key, value),
    )


def _assert_integrity(connection: sqlite3.Connection) -> None:
    result = connection.execute("PRAGMA quick_check").fetchone()
    if result != ("ok",):
        raise sqlite3.DatabaseError(f"SQLite integrity check failed: {result!r}")


def backup_database(database_path: Path, backup_path: Path) -> None:
    database_path = Path(database_path)
    backup_path = Path(backup_path)
    if not database_path.is_file():
        raise FileNotFoundError(database_path)
    if database_path.resolve() == backup_path.resolve():
        raise ValueError("backup path must differ from database path")
    if backup_path.exists():
        raise FileExistsError(backup_path)

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(database_path)
    destination = sqlite3.connect(backup_path)
    try:
        _assert_integrity(source)
        source.backup(destination)
        _assert_integrity(destination)
    except Exception:
        destination.close()
        source.close()
        if backup_path.exists():
            backup_path.unlink()
        raise
    else:
        destination.close()
        source.close()


def restore_database(backup_path: Path, database_path: Path) -> None:
    backup_path = Path(backup_path)
    database_path = Path(database_path)
    if not backup_path.is_file():
        raise FileNotFoundError(backup_path)
    if backup_path.resolve() == database_path.resolve():
        raise ValueError("backup path must differ from database path")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{database_path.name}.",
        suffix=".restore",
        dir=database_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    source = sqlite3.connect(backup_path)
    destination = sqlite3.connect(temporary_path)
    try:
        _assert_integrity(source)
        source.backup(destination)
        _assert_integrity(destination)
        destination.close()
        source.close()
        os.replace(temporary_path, database_path)
    except Exception:
        destination.close()
        source.close()
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def migrate_database(
    database_path: Path,
    backup_path: Path,
    *,
    migration: Callable[[sqlite3.Connection], None] = apply_migrations,
) -> None:
    database_path = Path(database_path)
    backup_path = Path(backup_path)
    backup_database(database_path, backup_path)

    connection = sqlite3.connect(database_path)
    try:
        migration(connection)
        _assert_integrity(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        connection.close()
        restore_database(backup_path, database_path)
        raise
    else:
        connection.close()
