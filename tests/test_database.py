import sqlite3
from pathlib import Path
import tempfile
import unittest

from alfa_sync_bot.database import (
    apply_migrations,
    backup_database,
    migrate_database,
    restore_database,
)


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

    def test_backup_and_restore_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "bot.sqlite3"
            backup_path = root / "backups" / "before-migration.sqlite3"
            connection = sqlite3.connect(database_path)
            apply_migrations(connection)
            connection.execute(
                "INSERT INTO import_runs (source, started_at, status) "
                "VALUES ('test', '2026-09-04T00:00:00+00:00', 'completed')"
            )
            connection.commit()
            connection.close()

            backup_database(database_path, backup_path)
            connection = sqlite3.connect(database_path)
            connection.execute("DELETE FROM import_runs")
            connection.commit()
            connection.close()
            restore_database(backup_path, database_path)

            restored = sqlite3.connect(database_path)
            count = restored.execute("SELECT COUNT(*) FROM import_runs").fetchone()[0]
            restored.close()
            self.assertEqual(count, 1)

    def test_failed_migration_automatically_restores_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "bot.sqlite3"
            backup_path = root / "backups" / "rollback.sqlite3"
            connection = sqlite3.connect(database_path)
            apply_migrations(connection)
            connection.execute(
                "INSERT INTO import_runs (source, started_at, status) "
                "VALUES ('keep', '2026-09-04T00:00:00+00:00', 'completed')"
            )
            connection.commit()
            connection.close()

            def broken_migration(connection):
                connection.execute("DELETE FROM import_runs")
                connection.commit()
                raise RuntimeError("simulated migration failure")

            with self.assertRaisesRegex(RuntimeError, "simulated"):
                migrate_database(
                    database_path,
                    backup_path,
                    migration=broken_migration,
                )

            restored = sqlite3.connect(database_path)
            sources = restored.execute("SELECT source FROM import_runs").fetchall()
            restored.close()
            self.assertEqual(sources, [("keep",)])


if __name__ == "__main__":
    unittest.main()
