import sqlite3
import unittest

from alfa_sync_bot.database import apply_migrations


class DatabaseTests(unittest.TestCase):
    def test_first_migration_creates_schedule_and_finance_foundation(self):
        connection = sqlite3.connect(":memory:")

        apply_migrations(connection)

        objects = {
            (row[0], row[1])
            for row in connection.execute(
                "SELECT type, name FROM sqlite_master "
                "WHERE type IN ('table', 'view')"
            )
        }
        self.assertTrue(
            {
                ("table", "schema_migrations"),
                ("table", "import_runs"),
                ("table", "lessons"),
                ("table", "lesson_changes"),
                ("table", "notification_deliveries"),
                ("table", "pay_rules"),
                ("table", "income_accruals"),
                ("table", "payment_periods"),
                ("view", "finance_events"),
            }.issubset(objects)
        )
        rules = connection.execute(
            "SELECT duration_minutes, amount_minor FROM pay_rules "
            "ORDER BY duration_minutes"
        ).fetchall()
        self.assertEqual(rules, [(30, 40000), (60, 80000), (90, 120000)])


if __name__ == "__main__":
    unittest.main()
