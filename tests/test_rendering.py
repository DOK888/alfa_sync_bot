import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from alfa_sync_bot.rendering import render_analysis
from alfa_sync_bot.replacement_service import AnalyzedOffer, ResultCategory


class RenderingTests(unittest.TestCase):
    def test_renders_sorted_information_without_actions(self):
        timezone = ZoneInfo("Asia/Yekaterinburg")
        items = [
            AnalyzedOffer(
                name="Group A",
                start=datetime(2026, 9, 5, 14, 0, tzinfo=timezone),
                end=datetime(2026, 9, 5, 15, 0, tzinfo=timezone),
                category=ResultCategory.AVAILABLE,
            ),
            AnalyzedOffer(
                name="Group B",
                start=datetime(2026, 9, 5, 14, 30, tzinfo=timezone),
                end=datetime(2026, 9, 5, 15, 30, tzinfo=timezone),
                category=ResultCategory.SHIFTABLE,
                shift_minutes=(30,),
            ),
        ]

        result = render_analysis(items)

        self.assertIn("Можно взять", result)
        self.assertIn("Group A — 14:00–15:00 ЕКБ", result)
        self.assertIn("Можно со сдвигом до 30 минут", result)
        self.assertIn("Group B — +30 мин → 15:00–16:00 ЕКБ", result)
        self.assertNotIn("кнопк", result.lower())
        self.assertNotIn("подтверд", result.lower())

    def test_renders_conditional_unavailable_and_review_sections(self):
        timezone = ZoneInfo("Asia/Yekaterinburg")
        start = datetime(2026, 9, 5, 14, 0, tzinfo=timezone)
        end = datetime(2026, 9, 5, 15, 0, tzinfo=timezone)
        items = [
            AnalyzedOffer(
                name="Group A",
                start=start,
                end=end,
                category=ResultCategory.CONDITIONAL,
                conflicts_with=("Group B",),
            ),
            AnalyzedOffer(
                name="Group C",
                start=start,
                end=end,
                category=ResultCategory.UNAVAILABLE,
            ),
            AnalyzedOffer(
                name="Group D",
                start=start,
                end=end,
                category=ResultCategory.REVIEW_REQUIRED,
            ),
        ]

        result = render_analysis(items)

        self.assertIn("Можно, если не брать другое предложение", result)
        self.assertIn("Group A — если не брать: Group B", result)
        self.assertIn("Нельзя взять", result)
        self.assertIn("Требует проверки", result)


if __name__ == "__main__":
    unittest.main()
