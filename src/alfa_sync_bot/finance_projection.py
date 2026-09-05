import sqlite3


def _rate_for_lesson(
    connection: sqlite3.Connection, duration_minutes: int, lesson_day: str
) -> tuple[int, int] | None:
    row = connection.execute(
        "SELECT id, amount_minor FROM pay_rules "
        "WHERE duration_minutes = ? AND effective_from <= ? "
        "AND (effective_to IS NULL OR effective_to >= ?) "
        "ORDER BY effective_from DESC LIMIT 1",
        (duration_minutes, lesson_day, lesson_day),
    ).fetchone()
    return None if row is None else (row[0], row[1])


def reconcile_income_accruals(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        "SELECT id, start_at, end_at, duration_minutes, status, deleted_at "
        "FROM lessons"
    ).fetchall()
    with connection:
        for lesson_id, start_at, end_at, duration_minutes, status, deleted_at in rows:
            if deleted_at is not None or status == "cancelled":
                connection.execute(
                    "DELETE FROM income_accruals WHERE lesson_id = ? AND status = 'planned'",
                    (lesson_id,),
                )
                continue
            rate = _rate_for_lesson(connection, duration_minutes, start_at[:10])
            if rate is None:
                continue
            pay_rule_id, amount_minor = rate
            if status == "conducted":
                connection.execute(
                    "INSERT INTO income_accruals "
                    "(lesson_id, pay_rule_id, amount_minor, status, earned_at) "
                    "VALUES (?, ?, ?, 'earned', ?) "
                    "ON CONFLICT(lesson_id) DO UPDATE SET "
                    "pay_rule_id = excluded.pay_rule_id, amount_minor = excluded.amount_minor, "
                    "status = CASE WHEN income_accruals.status = 'paid' THEN 'paid' ELSE 'earned' END, "
                    "earned_at = COALESCE(income_accruals.earned_at, excluded.earned_at)",
                    (lesson_id, pay_rule_id, amount_minor, end_at),
                )
            elif status == "planned":
                connection.execute(
                    "INSERT INTO income_accruals "
                    "(lesson_id, pay_rule_id, amount_minor, status) "
                    "VALUES (?, ?, ?, 'planned') "
                    "ON CONFLICT(lesson_id) DO UPDATE SET "
                    "pay_rule_id = excluded.pay_rule_id, amount_minor = excluded.amount_minor "
                    "WHERE income_accruals.status = 'planned'",
                    (lesson_id, pay_rule_id, amount_minor),
                )
