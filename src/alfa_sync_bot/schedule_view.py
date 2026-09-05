from datetime import date, datetime
import sqlite3


def render_schedule(
    connection: sqlite3.Connection, start_day: date, end_day: date
) -> str:
    rows = connection.execute(
        "SELECT group_name, start_at, end_at FROM lessons "
        "WHERE deleted_at IS NULL AND status != 'cancelled' "
        "AND substr(start_at, 1, 10) BETWEEN ? AND ? "
        "ORDER BY start_at, group_name COLLATE NOCASE",
        (start_day.isoformat(), end_day.isoformat()),
    ).fetchall()
    if not rows:
        return "На этот период уроков нет."

    lines: list[str] = []
    for group_name, start_at, end_at in rows:
        start = datetime.fromisoformat(start_at)
        end = datetime.fromisoformat(end_at)
        lines.append(f"• {group_name} — {start:%H:%M}–{end:%H:%M} ЕКБ")
    return "\n".join(lines)
