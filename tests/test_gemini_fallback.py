from datetime import date
import json
import unittest

from alfa_sync_bot.gemini_fallback import parse_gemini_draft


class GeminiFallbackTests(unittest.TestCase):
    def test_valid_json_draft_becomes_canonical_replacement_text(self):
        payload = json.dumps(
            {
                "offers": [
                    {
                        "name": "Synthetic Group",
                        "date": "2026-09-06",
                        "start": "12:00",
                        "end": "13:00",
                        "duration_minutes": 60,
                        "replacement_type": "Разовая",
                    }
                ]
            }
        )

        canonical = parse_gemini_draft(payload, reference_date=date(2026, 9, 5))

        self.assertEqual(
            canonical,
            "06.09.2026 Разовая\nSynthetic Group (60 минут) 12:00 — 13:00",
        )

    def test_draft_with_an_invalid_time_is_rejected(self):
        payload = json.dumps(
            {
                "offers": [
                    {
                        "name": "Synthetic Group",
                        "date": "2026-09-06",
                        "start": "25:00",
                        "end": "13:00",
                        "duration_minutes": 60,
                        "replacement_type": "Разовая",
                    }
                ]
            }
        )

        self.assertIsNone(parse_gemini_draft(payload, reference_date=date(2026, 9, 5)))

