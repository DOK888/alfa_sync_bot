import sqlite3
import unittest
from datetime import date

from alfa_sync_bot.database import apply_migrations
from alfa_sync_bot.schedule_view import render_schedule


class ScheduleViewTests(unittest.TestCase):
    def test_renders_active_ekb_lessons_in_time_order(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        connection.executemany(
            "INSERT INTO lessons (source, external_lesson_id, group_name, start_at, end_at, duration_minutes, status) VALUES ('x', ?, ?, ?, ?, 60, ?)",
            [
                ("later", "Later", "2026-09-07T16:00:00+05:00", "2026-09-07T17:00:00+05:00", "planned"),
                ("early", "Early", "2026-09-07T12:00:00+05:00", "2026-09-07T13:00:00+05:00", "planned"),
                ("cancelled", "Cancelled", "2026-09-07T14:00:00+05:00", "2026-09-07T15:00:00+05:00", "cancelled"),
            ],
        )

        result = render_schedule(connection, date(2026, 9, 7), date(2026, 9, 7))

        self.assertIn("Early — 12:00–13:00 ЕКБ", result)
        self.assertIn("Later — 16:00–17:00 ЕКБ", result)
        self.assertNotIn("Cancelled", result)
        self.assertLess(result.index("Early"), result.index("Later"))

    def test_renders_empty_schedule_without_lesson_data(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)

        self.assertEqual(
            render_schedule(connection, date(2026, 9, 7), date(2026, 9, 7)),
            "На этот период уроков нет.",
        )
