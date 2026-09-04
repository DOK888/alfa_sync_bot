import unittest
from datetime import date
import sqlite3

from alfa_sync_bot.database import apply_migrations
from alfa_sync_bot.finance import income_overview, previous_month_bounds, week_bounds


class FinanceTests(unittest.TestCase):
    def test_week_runs_from_monday_through_sunday(self):
        start, end = week_bounds(date(2026, 9, 3))

        self.assertEqual(start, date(2026, 8, 31))
        self.assertEqual(end, date(2026, 9, 6))

    def test_previous_month_bounds_cross_year_boundary(self):
        start, end = previous_month_bounds(date(2026, 1, 15))

        self.assertEqual(start, date(2025, 12, 1))
        self.assertEqual(end, date(2025, 12, 31))

    def test_income_overview_separates_earned_periods_from_future_plans(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        lessons = [
            ("aug", "2026-08-20T14:00:00+05:00", "2026-08-20T15:00:00+05:00", "conducted"),
            ("week", "2026-09-03T14:00:00+05:00", "2026-09-03T15:30:00+05:00", "conducted"),
            ("future1", "2026-09-08T14:00:00+05:00", "2026-09-08T14:30:00+05:00", "planned"),
            ("future2", "2026-09-15T14:00:00+05:00", "2026-09-15T15:00:00+05:00", "planned"),
        ]
        for external_id, start, end, status in lessons:
            connection.execute(
                "INSERT INTO lessons (source, external_lesson_id, group_name, start_at, end_at, duration_minutes, status) VALUES (?, ?, 'G', ?, ?, ?, ?)",
                ("alfacrm", external_id, start, end, 90 if external_id == "week" else (30 if external_id == "future1" else 60), status),
            )
        ids = dict(connection.execute("SELECT external_lesson_id, id FROM lessons"))
        connection.executemany(
            "INSERT INTO income_accruals (lesson_id, amount_minor, status, earned_at) VALUES (?, ?, ?, ?)",
            [
                (ids["aug"], 80000, "earned", "2026-08-20T15:00:00+05:00"),
                (ids["week"], 120000, "earned", "2026-09-03T15:30:00+05:00"),
                (ids["future1"], 40000, "planned", None),
                (ids["future2"], 80000, "planned", None),
            ],
        )

        overview = income_overview(connection, date(2026, 9, 4))

        self.assertEqual(overview.previous_month_earned_minor, 80000)
        self.assertEqual(overview.current_week_earned_minor, 120000)
        self.assertEqual(
            overview.future_weeks_planned_minor,
            ((date(2026, 9, 7), 40000), (date(2026, 9, 14), 80000)),
        )


if __name__ == "__main__":
    unittest.main()
