from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from alfa_sync_bot.__main__ import main


class CliTests(unittest.TestCase):
    def test_shadow_command_outputs_aggregate_counts_only(self):
        payload = {
            "tetrika": {
                "lessons": [
                    {
                        "date": "05.09.2026",
                        "start": "12:00",
                        "end": "13:00",
                        "group": "Synthetic Group",
                        "duration": 60,
                        "status": "planned",
                    }
                ]
            },
            "wellkid": {"lessons": []},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "report.json"
            database_path = root / "state" / "shadow.sqlite3"
            report_path.write_text(json.dumps(payload), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "shadow",
                        "--report",
                        str(report_path),
                        "--database",
                        str(database_path),
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                "changes": {"changed": 0, "deleted": 0, "new": 1},
                "complete_sources": 2,
                "rejected_lessons": 0,
            },
        )

    def test_shadow_command_returns_nonzero_for_missing_report(self):
        output = io.StringIO()
        errors = io.StringIO()

        with redirect_stdout(output), redirect_stderr(errors):
            exit_code = main(
                [
                    "shadow",
                    "--report",
                    "does-not-exist.json",
                    "--database",
                    "state.sqlite3",
                ]
            )

        self.assertEqual(exit_code, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("shadow import failed", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
