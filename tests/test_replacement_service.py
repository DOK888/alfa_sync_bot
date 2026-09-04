import unittest

from alfa_sync_bot.replacement_service import ResultCategory, analyze_message
from alfa_sync_bot.replacement_parser import MessageEntity


class ReplacementServiceTests(unittest.TestCase):
    def test_analysis_converts_time_and_separates_duration_mismatch(self):
        message = (
            "05.09.2026 Постоянная замена\n"
            "Group A (60 минут) 12:00 — 13:00\n"
            "Group B (60 минут) 13:00 — 14:30"
        )

        result = analyze_message(message, scheduled=[])

        self.assertEqual(result[0].category, ResultCategory.AVAILABLE)
        self.assertEqual(result[0].start.isoformat(), "2026-09-05T14:00:00+05:00")
        self.assertEqual(result[0].end.isoformat(), "2026-09-05T15:00:00+05:00")
        self.assertEqual(result[1].category, ResultCategory.REVIEW_REQUIRED)

    def test_analysis_excludes_struck_telegram_offer(self):
        active = "Group A (60 минут) 12:00 — 13:00"
        struck = "Group B (60 минут) 13:00 — 14:00"
        message = f"05.09.2026 Разовая\n{active}\n{struck}"

        result = analyze_message(
            message,
            scheduled=[],
            entities=(
                MessageEntity(
                    kind="strikethrough",
                    offset=message.index(struck),
                    length=len(struck),
                ),
            ),
        )

        self.assertEqual([item.name for item in result], ["Group A"])


if __name__ == "__main__":
    unittest.main()
