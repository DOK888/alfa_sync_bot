import sqlite3
import unittest

from alfa_sync_bot.database import apply_migrations
from alfa_sync_bot.finance_projection import reconcile_income_accruals


class FinanceProjectionTests(unittest.TestCase):
    def test_projects_rate_and_earned_status_from_conducted_crm_lesson(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        connection.execute(
            "INSERT INTO lessons (source, external_lesson_id, group_name, start_at, end_at, duration_minutes, status) VALUES ('x', 'conducted', 'G', '2026-09-05T12:00:00+05:00', '2026-09-05T13:30:00+05:00', 90, 'conducted')"
        )

        reconcile_income_accruals(connection)

        self.assertEqual(
            connection.execute("SELECT amount_minor, status, earned_at FROM income_accruals").fetchone(),
            (120000, "earned", "2026-09-05T13:30:00+05:00"),
        )

    def test_cancellation_removes_a_planned_accrual(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        connection.execute(
            "INSERT INTO lessons (source, external_lesson_id, group_name, start_at, end_at, duration_minutes, status) VALUES ('x', 'planned', 'G', '2026-09-08T12:00:00+05:00', '2026-09-08T13:00:00+05:00', 60, 'planned')"
        )
        reconcile_income_accruals(connection)
        connection.execute("UPDATE lessons SET status = 'cancelled' WHERE external_lesson_id = 'planned'")

        reconcile_income_accruals(connection)

        self.assertIsNone(connection.execute("SELECT 1 FROM income_accruals").fetchone())
