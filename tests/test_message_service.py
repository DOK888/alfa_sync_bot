from datetime import datetime
import sqlite3
import unittest

from alfa_sync_bot.database import apply_migrations
from alfa_sync_bot.message_service import analyze_replacement_text


class MessageServiceTests(unittest.TestCase):
    def test_uses_sqlite_schedule_and_returns_information_only(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        connection.execute(
            "INSERT INTO lessons "
            "(source, external_lesson_id, group_name, start_at, end_at, duration_minutes, status) "
            "VALUES ('legacy:tetrika', 'one', 'Existing Group', ?, ?, 60, 'planned')",
            ("2026-09-05T16:00:00+05:00", "2026-09-05T17:00:00+05:00"),
        )
        message = (
            "05.09.2026 Разовая\n"
            "New Group (60 минут) 12:00 — 13:00"
        )

        rendered = analyze_replacement_text(message, connection)

        self.assertIn("✅ Можно взять", rendered)
        self.assertIn("New Group", rendered)
        self.assertNotIn("взята", rendered.lower())

    def test_reports_when_message_contains_no_supported_offers(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)

        rendered = analyze_replacement_text("обычный текст", connection)

        self.assertEqual(rendered, "Не нашёл предложений замены в сообщении.")


if __name__ == "__main__":
    unittest.main()
