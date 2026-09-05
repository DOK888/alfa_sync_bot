import unittest
from scripts.prepare_owner_config import extract_owner


class OwnerConfigTests(unittest.TestCase):
    def test_extracts_literal_without_executing_source(self):
        self.assertEqual(extract_owner('raise RuntimeError()\nALLOWED_USER_ID = 1001'), 1001)

    def test_missing_ambiguous_or_computed_identity_is_rejected(self):
        for source in ('', 'ALLOWED_USER_ID = True', 'ALLOWED_USER_ID = -1',
                       'ALLOWED_USER_ID = int("1001")',
                       'ALLOWED_USER_ID = 1001\nALLOWED_USER_ID = 2002'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                extract_owner(source)
