from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3

from .database import apply_migrations
from .legacy_report import parse_legacy_report
from .lesson_sync import reconcile_snapshot


@dataclass(frozen=True)
class ShadowResult:
    change_counts: dict[str, int]
    complete_sources: set[str]
    rejected_lesson_count: int


def run_shadow_import(report_path: Path, database_path: Path) -> ShadowResult:
    report_path = Path(report_path)
    database_path = Path(database_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("legacy report root must be an object")

    parsed = parse_legacy_report(payload)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    change_counts = {"new": 0, "changed": 0, "deleted": 0}
    try:
        apply_migrations(connection)
        for source, lessons in parsed.lessons_by_source.items():
            changes = reconcile_snapshot(
                connection,
                source,
                lessons,
                complete=source in parsed.complete_sources,
            )
            for change in changes:
                change_counts[change.change_type] += 1
    finally:
        connection.close()

    return ShadowResult(
        change_counts=change_counts,
        complete_sources=parsed.complete_sources,
        rejected_lesson_count=parsed.rejected_lesson_count,
    )
