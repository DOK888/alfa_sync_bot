import sqlite3
import unittest

from alfa_sync_bot.database import apply_migrations
from alfa_sync_bot.notifications import deliver_pending_notifications, register_chat


class NotificationTests(unittest.TestCase):
    def _change(self, connection, change_id, group_name="Group"):
        connection.execute(
            "INSERT INTO lessons (id, source, external_lesson_id, group_name, start_at, end_at, duration_minutes, status) VALUES (?, 'x', ?, ?, '2026-09-07T12:00:00+05:00', '2026-09-07T13:00:00+05:00', 60, 'planned')",
            (change_id, f"lesson-{change_id}", group_name),
        )
        connection.execute(
            "INSERT INTO import_runs (id, source, started_at, completed_at, status) VALUES (?, 'x', '2026-09-01T00:00:00+00:00', '2026-09-01T00:00:00+00:00', 'completed')",
            (change_id,),
        )
        connection.execute(
            "INSERT INTO lesson_changes (id, lesson_id, import_run_id, change_type, changed_fields_json, event_hash, created_at) VALUES (?, ?, ?, 'new', '{}', ?, '2026-09-01T00:00:00+00:00')",
            (change_id, change_id, change_id, f"event-{change_id}"),
        )

    def test_registration_skips_changes_that_existed_before_start(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        self._change(connection, 1)
        register_chat(connection, 1001)
        sent = []

        delivered = deliver_pending_notifications(connection, lambda chat_id, text: sent.append((chat_id, text)))

        self.assertEqual(delivered, 0)
        self.assertEqual(sent, [])

    def test_new_change_is_delivered_once_after_registration(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        register_chat(connection, 1001)
        self._change(connection, 1, "Synthetic Group")
        sent = []

        first = deliver_pending_notifications(connection, lambda chat_id, text: sent.append((chat_id, text)))
        second = deliver_pending_notifications(connection, lambda chat_id, text: sent.append((chat_id, text)))

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(len(sent), 1)
        self.assertIn("Synthetic Group", sent[0][1])

    def test_failed_send_does_not_mark_notification_delivered(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        register_chat(connection, 1001)
        self._change(connection, 1)

        with self.assertRaises(RuntimeError):
            deliver_pending_notifications(connection, lambda _chat_id, _text: (_ for _ in ()).throw(RuntimeError("offline")))

        self.assertIsNone(connection.execute("SELECT 1 FROM notification_deliveries").fetchone())
