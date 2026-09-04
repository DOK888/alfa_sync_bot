import unittest

from alfa_sync_bot.replacement_parser import MessageEntity, parse_replacement_message
from datetime import date


class ReplacementParserTests(unittest.TestCase):
    def test_tomorrow_heading_uses_message_date_as_context(self):
        message = (
            "Срочная замена на завтра\n"
            "Python_1 (60 минут) 12:00 — 13:00"
        )

        parsed = parse_replacement_message(
            message, reference_date=date(2026, 9, 5)
        )

        self.assertEqual(len(parsed.offers), 1)
        self.assertEqual(parsed.offers[0].start.isoformat(), "2026-09-06T12:00:00+03:00")

    def test_russian_and_short_date_headings_apply_to_following_offers(self):
        message = (
            "5 сентября\n"
            "Stencyl_16 (90 минут) 10:30 — 12:00\n"
            "Постоянная замена с 05.09\n"
            "Lua_233 (90 минут) 15:00 — 16:30"
        )

        parsed = parse_replacement_message(message, reference_year=2026)

        self.assertEqual(len(parsed.offers), 2)
        self.assertEqual(parsed.offers[0].start.isoformat(), "2026-09-05T10:30:00+03:00")
        self.assertEqual(parsed.offers[1].start.isoformat(), "2026-09-05T15:00:00+03:00")

    def test_telegram_utf16_offsets_are_converted_before_masking(self):
        active = "Group A (60 минут) 12:00 - 13:00"
        struck = "Group B (60 минут) 13:00 - 14:00"
        message = f"🔥\n05.09.2026 Разовая\n{active}\n{struck}"
        python_start = message.index(struck)
        telegram_start = len(message[:python_start].encode("utf-16-le")) // 2
        telegram_length = len(struck.encode("utf-16-le")) // 2

        result = parse_replacement_message(
            message,
            entities=(
                MessageEntity(
                    kind="strikethrough",
                    offset=telegram_start,
                    length=telegram_length,
                ),
            ),
        )

        self.assertEqual([offer.name for offer in result.offers], ["Group A"])

    def test_date_heading_applies_to_following_offer(self):
        message = (
            "05.09.2026 Постоянная замена\n"
            "Group A (90 минут) 12:30 — 14:00"
        )

        result = parse_replacement_message(message)

        self.assertEqual(len(result.offers), 1)
        offer = result.offers[0]
        self.assertEqual(offer.name, "Group A")
        self.assertEqual(offer.replacement_type, "Постоянная замена")
        self.assertEqual(offer.start.isoformat(), "2026-09-05T12:30:00+03:00")
        self.assertEqual(offer.end.isoformat(), "2026-09-05T14:00:00+03:00")
        self.assertEqual(offer.declared_duration_minutes, 90)

    def test_fully_struck_offer_is_ignored(self):
        active = "Group A (60 минут) 12:00 - 13:00"
        struck = "Group B (90 минут) 13:00 - 14:30"
        message = f"05.09.2026 Разовая\n{active}\n{struck}"
        struck_start = message.index(struck)

        result = parse_replacement_message(
            message,
            entities=(
                MessageEntity(
                    kind="strikethrough",
                    offset=struck_start,
                    length=len(struck),
                ),
            ),
        )

        self.assertEqual([offer.name for offer in result.offers], ["Group A"])

    def test_duration_mismatch_is_marked_for_review(self):
        message = (
            "07.09.2026 Постоянная замена\n"
            "Group A (60 минут) 17:30 — 19:00"
        )

        offer = parse_replacement_message(message).offers[0]

        self.assertEqual(offer.actual_duration_minutes, 90)
        self.assertFalse(offer.duration_matches)

    def test_group_id_is_read_from_telegram_text_link(self):
        offer_line = "Group A (60 минут) 12:00 — 13:00"
        message = f"05.09.2026 Разовая\n{offer_line}"
        group_start = message.index("Group A")

        offer = parse_replacement_message(
            message,
            entities=(
                MessageEntity(
                    kind="text_link",
                    offset=group_start,
                    length=len("Group A"),
                    url="https://example.invalid/group/view?id=4239",
                ),
            ),
        ).offers[0]

        self.assertEqual(offer.external_group_id, "4239")


if __name__ == "__main__":
    unittest.main()
