import sqlite3
import unittest

from alfa_sync_bot.database import apply_migrations, get_runtime_state
from alfa_sync_bot.shadow import consume_import_request, request_import


class ImportRequestTests(unittest.TestCase):
    def test_shadow_consumes_a_manual_import_request_once(self):
        connection = sqlite3.connect(":memory:")
        apply_migrations(connection)

        request_import(connection)

        self.assertTrue(consume_import_request(connection))
        self.assertFalse(consume_import_request(connection))
        self.assertEqual(get_runtime_state(connection, "shadow.import_requested"), "0")
