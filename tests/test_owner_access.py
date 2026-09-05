import os
import sqlite3
import unittest
from unittest.mock import patch

from alfa_sync_bot.database import apply_migrations, get_runtime_state
from alfa_sync_bot.telegram_runtime import process_updates
from alfa_sync_bot.notifications import deliver_pending_notifications, register_chat


class Client:
    def __init__(self, messages):
        self.messages = messages
        self.sent = []

    def get_updates(self, offset):
        return self.messages

    def send_message(self, *args, **kwargs):
        self.sent.append(args)


class OwnerAccessTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        apply_migrations(self.connection)
        self.addCleanup(self.connection.close)
        self.env = patch.dict(os.environ, {'TELEGRAM_ALLOWED_USER_ID': '1001'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_all_foreign_requests_are_ignored_before_analysis_or_registration(self):
        texts = ['/start', 'Меню', '📅 На сегодня', '🗓 На неделю', '💰 Мои финансы',
                 '🔄 Собрать данные сейчас', 'Новая замена',
                 '05.09.2026 Разовая\nTest (60 минут) 12:00 — 13:00']
        client = Client([{'update_id': i, 'message': {
            'chat': {'id': 2002, 'type': 'private'}, 'from': {'id': 2002}, 'text': text
        }} for i, text in enumerate(texts)])
        class ForbiddenFallback:
            def canonicalize(self, *args):
                raise AssertionError('Unauthorized data reached AI')
        process_updates(client, self.connection, fallback=ForbiddenFallback())
        self.assertEqual(client.sent, [])
        self.assertEqual(self.connection.execute('SELECT count(*) FROM telegram_chats').fetchone()[0], 0)
        self.assertIsNone(get_runtime_state(self.connection, 'shadow.import_requested'))

    def test_owner_in_group_and_missing_or_mismatched_sender_are_rejected(self):
        messages = [
            {'chat': {'id': -1, 'type': 'group'}, 'from': {'id': 1001}},
            {'chat': {'id': 1001, 'type': 'private'}},
            {'chat': {'id': 1001, 'type': 'private'}, 'from': {'id': 2002}},
        ]
        client = Client([{'update_id': i, 'message': dict(m, text='/start')} for i, m in enumerate(messages)])
        process_updates(client, self.connection)
        self.assertEqual(client.sent, [])

    def test_missing_owner_fails_closed(self):
        with patch.dict(os.environ, {'TELEGRAM_ALLOWED_USER_ID': ''}):
            with self.assertRaises(ValueError):
                process_updates(Client([]), self.connection)

    def test_foreign_registration_is_rejected(self):
        with self.assertRaises(PermissionError):
            register_chat(self.connection, 2002)

    def test_preexisting_foreign_subscriber_never_receives_notifications(self):
        self.connection.execute('INSERT INTO telegram_chats(chat_id) VALUES (2002)')
        self.connection.execute("INSERT INTO lessons(id, source, external_lesson_id, group_name, start_at, end_at, duration_minutes,status) VALUES(1,'test','1','Synthetic','2026-09-05T12:00:00+05:00','2026-09-05T13:00:00+05:00',60,'planned')")
        self.connection.execute("INSERT INTO import_runs(id,source,started_at,status) VALUES(1,'test','2026-09-05','completed')")
        self.connection.execute("INSERT INTO lesson_changes(lesson_id,import_run_id,change_type,changed_fields_json,event_hash,created_at) VALUES(1,1,'new','{}','test','2026-09-05')")
        sent = []
        deliver_pending_notifications(self.connection, lambda *args: sent.append(args))
        self.assertEqual(sent, [])

    def test_owner_private_start_works(self):
        client = Client([{'update_id': 1, 'message': {'chat': {'id': 1001, 'type': 'private'}, 'from': {'id': 1001}, 'text': '/start'}}])
        process_updates(client, self.connection)
        self.assertEqual(len(client.sent), 1)
