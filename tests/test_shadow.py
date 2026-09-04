import json
from pathlib import Path
import tempfile
import unittest

from alfa_sync_bot.shadow import run_shadow_import


def _payload(start: str = "12:00") -> dict[str, object]:
    return {
        "tetrika": {
            "lessons": [
                {
                    "date": "05.09.2026",
                    "start": start,
                    "end": "13:00",
                    "group": "Python 253",
                    "duration": 60,
                    "status": "planned",
                }
            ]
        },
        "wellkid": {"lessons": []},
    }


class ShadowImportTests(unittest.TestCase):
    def test_imports_each_school_once_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "legacy.json"
            database_path = root / "state" / "shadow.sqlite3"
            report_path.write_text(json.dumps(_payload()), encoding="utf-8")

            first = run_shadow_import(report_path, database_path)
            repeated = run_shadow_import(report_path, database_path)

        self.assertEqual(first.change_counts, {"new": 1, "changed": 0, "deleted": 0})
        self.assertEqual(first.complete_sources, {"legacy:tetrika", "legacy:wellkid"})
        self.assertEqual(repeated.change_counts, {"new": 0, "changed": 0, "deleted": 0})

    def test_incomplete_report_cannot_delete_existing_lessons(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "legacy.json"
            database_path = root / "shadow.sqlite3"
            report_path.write_text(json.dumps(_payload()), encoding="utf-8")
            run_shadow_import(report_path, database_path)
            report_path.write_text(
                json.dumps({"tetrika": {"lessons": [{"date": "broken"}]}}),
                encoding="utf-8",
            )

            result = run_shadow_import(report_path, database_path)

        self.assertEqual(result.change_counts["deleted"], 0)
        self.assertNotIn("legacy:tetrika", result.complete_sources)
        self.assertEqual(result.rejected_lesson_count, 1)


if __name__ == "__main__":
    unittest.main()
