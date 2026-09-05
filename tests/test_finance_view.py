import sqlite3
import unittest
from datetime import date

from alfa_sync_bot.database import apply_migrations
from alfa_sync_bot.finance_view import render_finance


class FinanceViewTests(unittest.TestCase):
    def test_renders_previous_month_current_week_and_future_weeks(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        connection.executemany(
            "INSERT INTO lessons (source, external_lesson_id, group_name, start_at, end_at, duration_minutes, status) VALUES ('x', ?, 'G', ?, ?, 60, ?)",
            [
                ("last", "2026-08-20T12:00:00+05:00", "2026-08-20T13:00:00+05:00", "conducted"),
                ("week", "2026-09-03T12:00:00+05:00", "2026-09-03T13:00:00+05:00", "conducted"),
                ("future", "2026-09-08T12:00:00+05:00", "2026-09-08T13:00:00+05:00", "planned"),
            ],
        )
        ids = dict(connection.execute("SELECT external_lesson_id, id FROM lessons"))
        connection.executemany(
            "INSERT INTO income_accruals (lesson_id, amount_minor, status, earned_at) VALUES (?, 80000, ?, ?)",
            [(ids["last"], "earned", "2026-08-20T13:00:00+05:00"), (ids["week"], "earned", "2026-09-03T13:00:00+05:00"), (ids["future"], "planned", None)],
        )

        result = render_finance(connection, date(2026, 9, 4))

        self.assertIn("Прошлый месяц: 800 ₽", result)
        self.assertIn("Эта неделя: 800 ₽", result)
        self.assertIn("07.09–13.09: 800 ₽", result)
