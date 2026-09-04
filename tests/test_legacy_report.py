import unittest

from alfa_sync_bot.legacy_report import parse_legacy_report


class LegacyReportTests(unittest.TestCase):
    def test_normalizes_valid_legacy_lessons_to_yekaterinburg_snapshots(self):
        payload = {
            "tetrika": {
                "lessons": [
                    {
                        "date": "05.09.2026",
                        "start": "12:00",
                        "end": "13:30",
                        "group": "Python 253",
                        "duration": 90,
                        "status": "planned",
                    }
                ]
            },
            "wellkid": {
                "lessons": [
                    {
                        "date": "06.09.2026",
                        "start": "14:00",
                        "end": "15:00",
                        "group": "Scratch 12",
                        "duration": 60,
                        "status": "conducted",
                    }
                ]
            },
        }

        report = parse_legacy_report(payload)

        tetrika_lesson = report.lessons_by_source["legacy:tetrika"][0]
        wellkid_lesson = report.lessons_by_source["legacy:wellkid"][0]
        self.assertEqual(tetrika_lesson.start_at, "2026-09-05T12:00:00+05:00")
        self.assertEqual(tetrika_lesson.end_at, "2026-09-05T13:30:00+05:00")
        self.assertEqual(tetrika_lesson.status, "planned")
        self.assertEqual(wellkid_lesson.status, "conducted")
        self.assertEqual(
            report.complete_sources, {"legacy:tetrika", "legacy:wellkid"}
        )

    def test_marks_source_incomplete_when_one_lesson_is_malformed(self):
        payload = {
            "tetrika": {
                "lessons": [
                    {
                        "date": "05.09.2026",
                        "start": "12:00",
                        "end": "13:00",
                        "group": "Python 253",
                        "duration": 60,
                        "status": "planned",
                    },
                    {"date": "not-a-date"},
                ]
            }
        }

        report = parse_legacy_report(payload)

        self.assertNotIn("legacy:tetrika", report.complete_sources)
        self.assertEqual(len(report.lessons_by_source["legacy:tetrika"]), 1)
        self.assertEqual(report.rejected_lesson_count, 1)

    def test_uses_same_fallback_identity_when_a_legacy_lesson_moves(self):
        base = {
            "date": "05.09.2026",
            "end": "13:00",
            "group": "Python 253",
            "duration": 60,
            "status": "planned",
        }
        first = parse_legacy_report({"tetrika": {"lessons": [{**base, "start": "12:00"}]}})
        moved = parse_legacy_report({"tetrika": {"lessons": [{**base, "start": "12:30"}]}})

        first_id = first.lessons_by_source["legacy:tetrika"][0].external_lesson_id
        moved_id = moved.lessons_by_source["legacy:tetrika"][0].external_lesson_id
        self.assertEqual(first_id, moved_id)


if __name__ == "__main__":
    unittest.main()
