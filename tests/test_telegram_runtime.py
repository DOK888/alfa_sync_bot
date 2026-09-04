import sqlite3
import unittest

from alfa_sync_bot.database import apply_migrations, get_runtime_state
from alfa_sync_bot.telegram_runtime import process_updates


class FakeTelegramClient:
    def __init__(self, updates):
        self.updates = updates
        self.requested_offsets = []
        self.sent_messages = []

    def get_updates(self, offset):
        self.requested_offsets.append(offset)
        return self.updates

    def send_message(self, chat_id, text):
        self.sent_messages.append((chat_id, text))


class TelegramRuntimeTests(unittest.TestCase):
    def test_recognized_offer_receives_reply_and_persists_next_offset(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        client = FakeTelegramClient(
            [
                {
                    "update_id": 41,
                    "message": {
                        "chat": {"id": 1001},
                        "text": "05.09.2026 Разовая\nPython_1 (60 минут) 12:00 — 13:00",
                    },
                }
            ]
        )

        next_offset = process_updates(client, connection)

        self.assertEqual(next_offset, 42)
        self.assertEqual(client.requested_offsets, [None])
        self.assertEqual(len(client.sent_messages), 1)
        self.assertEqual(client.sent_messages[0][0], 1001)
        self.assertIn("Можно взять", client.sent_messages[0][1])
        self.assertEqual(
            get_runtime_state(connection, "telegram.next_update_id"), "42"
        )

    def test_unrecognized_text_is_acknowledged_without_a_reply(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        client = FakeTelegramClient(
            [
                {
                    "update_id": 7,
                    "message": {"chat": {"id": 1001}, "text": "Привет"},
                }
            ]
        )

        process_updates(client, connection)

        self.assertEqual(client.sent_messages, [])
        self.assertEqual(
            get_runtime_state(connection, "telegram.next_update_id"), "8"
        )

    def test_stored_offset_is_used_after_a_restart(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        connection.execute(
            "INSERT INTO runtime_state (key, value) VALUES (?, ?)",
            ("telegram.next_update_id", "42"),
        )
        client = FakeTelegramClient([])

        process_updates(client, connection)

        self.assertEqual(client.requested_offsets, [42])
        self.assertEqual(client.sent_messages, [])
