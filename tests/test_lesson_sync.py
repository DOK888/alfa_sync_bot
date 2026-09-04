import sqlite3
import unittest

from alfa_sync_bot.database import apply_migrations
from alfa_sync_bot.lesson_sync import LessonSnapshot, reconcile_snapshot


class LessonSyncTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        apply_migrations(self.connection)

    def test_snapshot_reports_new_changed_and_deleted_without_duplicates(self):
        first = [
            LessonSnapshot("1", "g1", "Group A", "2026-09-05T14:00:00+05:00", "2026-09-05T15:00:00+05:00", "planned"),
            LessonSnapshot("2", "g2", "Group B", "2026-09-06T14:00:00+05:00", "2026-09-06T15:30:00+05:00", "planned"),
        ]

        initial = reconcile_snapshot(self.connection, "alfacrm", first, complete=True)
        repeated = reconcile_snapshot(self.connection, "alfacrm", first, complete=True)
        second = [
            LessonSnapshot("1", "g1", "Group A", "2026-09-05T15:00:00+05:00", "2026-09-05T16:00:00+05:00", "planned"),
            LessonSnapshot("3", "g3", "Group C", "2026-09-07T14:00:00+05:00", "2026-09-07T14:30:00+05:00", "planned"),
        ]
        changed = reconcile_snapshot(self.connection, "alfacrm", second, complete=True)

        self.assertEqual([item.change_type for item in initial], ["new", "new"])
        self.assertEqual(repeated, [])
        self.assertEqual(
            [(item.external_lesson_id, item.change_type) for item in changed],
            [("1", "changed"), ("3", "new"), ("2", "deleted")],
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM lesson_changes").fetchone()[0],
            5,
        )

    def test_incomplete_snapshot_never_marks_missing_lessons_deleted(self):
        lesson = LessonSnapshot("1", "g1", "Group A", "2026-09-05T14:00:00+05:00", "2026-09-05T15:00:00+05:00", "planned")
        reconcile_snapshot(self.connection, "alfacrm", [lesson], complete=True)

        changes = reconcile_snapshot(self.connection, "alfacrm", [], complete=False)

        self.assertEqual(changes, [])
        self.assertIsNone(
            self.connection.execute("SELECT deleted_at FROM lessons WHERE external_lesson_id = '1'").fetchone()[0]
        )


if __name__ == "__main__":
    unittest.main()
