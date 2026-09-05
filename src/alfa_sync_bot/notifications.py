from collections.abc import Callable
from datetime import datetime
import sqlite3
from .access import owner_id


def register_chat(connection: sqlite3.Connection, chat_id: int) -> None:
    if type(chat_id) is not int or chat_id != owner_id():
        raise PermissionError('Owner-only registration')
    watermark = connection.execute(
        "SELECT COALESCE(MAX(id), 0) FROM lesson_changes"
    ).fetchone()[0]
    with connection:
        connection.execute(
            "INSERT OR IGNORE INTO telegram_chats "
            "(chat_id, notification_after_change_id) VALUES (?, ?)",
            (chat_id, watermark),
        )


def _render_change(change_type: str, group_name: str, start_at: str, end_at: str) -> str:
    labels = {"new": "Добавлен", "changed": "Изменён", "deleted": "Удалён"}
    start = datetime.fromisoformat(start_at)
    end = datetime.fromisoformat(end_at)
    return f"• {labels[change_type]}: {group_name} — {start:%d.%m %H:%M}–{end:%H:%M} ЕКБ"


def deliver_pending_notifications(
    connection: sqlite3.Connection, send: Callable[[int, str], None]
) -> int:
    delivered = 0
    chats = connection.execute(
        "SELECT chat_id, notification_after_change_id FROM telegram_chats WHERE chat_id = ?",
        (owner_id(),),
    ).fetchall()
    for chat_id, watermark in chats:
        channel = f"telegram:{chat_id}"
        rows = connection.execute(
            "SELECT lesson_changes.id, lesson_changes.change_type, lessons.group_name, "
            "lessons.start_at, lessons.end_at FROM lesson_changes "
            "JOIN lessons ON lessons.id = lesson_changes.lesson_id "
            "WHERE lesson_changes.id > ? AND NOT EXISTS ("
            "SELECT 1 FROM notification_deliveries "
            "WHERE notification_deliveries.lesson_change_id = lesson_changes.id "
            "AND notification_deliveries.channel = ?) "
            "ORDER BY lesson_changes.id",
            (watermark, channel),
        ).fetchall()
        if not rows:
            continue
        text = "Расписание обновилось:\n" + "\n".join(
            _render_change(change_type, group_name, start_at, end_at)
            for _, change_type, group_name, start_at, end_at in rows
        )
        send(chat_id, text)
        with connection:
            connection.executemany(
                "INSERT OR IGNORE INTO notification_deliveries "
                "(lesson_change_id, channel, delivered_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                [(change_id, channel) for change_id, *_ in rows],
            )
        delivered += len(rows)
    return delivered
