import sqlite3
from datetime import date, datetime, timezone
import unittest

from alfa_sync_bot.database import apply_migrations, get_runtime_state
from alfa_sync_bot.telegram_runtime import message_reference_date, process_updates


class FakeTelegramClient:
    def __init__(self, updates):
        self.updates = updates
        self.requested_offsets = []
        self.sent_messages = []

    def get_updates(self, offset):
        self.requested_offsets.append(offset)
        return self.updates

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent_messages.append((chat_id, text, reply_markup))


class FakeFallback:
    def canonicalize(self, text, reference_date):
        return "06.09.2026 Разовая\nFallback_Group (60 минут) 12:00 — 13:00"


class TelegramRuntimeTests(unittest.TestCase):
    def test_start_registers_chat_and_sends_persistent_menu(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        client = FakeTelegramClient(
            [{"update_id": 1, "message": {"chat": {"id": 1001}, "text": "/start"}}]
        )

        process_updates(client, connection)

        self.assertEqual(client.sent_messages[0][0], 1001)
        self.assertIn("Готов", client.sent_messages[0][1])
        keyboard = client.sent_messages[0][2]
        self.assertTrue(keyboard["resize_keyboard"])
        self.assertIn(["📅 На сегодня", "🗓 На неделю"], keyboard["keyboard"])
        self.assertIn(["⚙️ Настройки ИИ"], keyboard["keyboard"])

    def test_today_menu_reads_schedule_without_replacement_analysis(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        connection.execute(
            "INSERT INTO lessons (source, external_lesson_id, group_name, start_at, end_at, duration_minutes, status) VALUES ('x', 'one', 'Group', '2026-09-05T12:00:00+05:00', '2026-09-05T13:00:00+05:00', 60, 'planned')"
        )
        client = FakeTelegramClient(
            [{"update_id": 2, "message": {"chat": {"id": 1001}, "date": int(datetime(2026, 9, 5, 7, tzinfo=timezone.utc).timestamp()), "text": "📅 На сегодня"}}]
        )

        process_updates(client, connection)

        self.assertIn("Group — 12:00–13:00 ЕКБ", client.sent_messages[0][1])

    def test_collect_now_requests_a_safe_shadow_import(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        client = FakeTelegramClient(
            [{"update_id": 3, "message": {"chat": {"id": 1001}, "text": "🔄 Собрать данные сейчас"}}]
        )

        process_updates(client, connection)

        self.assertIn("Запрос принят", client.sent_messages[0][1])
        self.assertEqual(get_runtime_state(connection, "shadow.import_requested"), "1")

    def test_report_and_ai_settings_buttons_receive_a_reply(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        client = FakeTelegramClient(
            [
                {"update_id": 4, "message": {"chat": {"id": 1001}, "text": "📝 Написать отчет"}},
                {"update_id": 5, "message": {"chat": {"id": 1001}, "text": "⚙️ Настройки ИИ"}},
            ]
        )

        process_updates(client, connection)

        self.assertEqual(len(client.sent_messages), 2)
        self.assertIn("Отчёт", client.sent_messages[0][1])
        self.assertIn("ИИ", client.sent_messages[1][1])

    def test_fallback_canonical_text_receives_an_availability_reply(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)
        client = FakeTelegramClient(
            [{"update_id": 1, "message": {"chat": {"id": 1001}, "text": "Новая замена"}}]
        )

        process_updates(client, connection, fallback=FakeFallback())

        self.assertEqual(len(client.sent_messages), 1)
        self.assertIn("Fallback_Group", client.sent_messages[0][1])

    def test_message_timestamp_becomes_yekaterinburg_reference_date(self):
        message = {
            "date": int(datetime(2026, 9, 5, 21, tzinfo=timezone.utc).timestamp())
        }

        self.assertEqual(message_reference_date(message), date(2026, 9, 6))

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
