from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3


@dataclass(frozen=True)
class LessonSnapshot:
    external_lesson_id: str
    external_group_id: str | None
    group_name: str
    start_at: str
    end_at: str
    status: str

    @property
    def duration_minutes(self) -> int:
        start = datetime.fromisoformat(self.start_at)
        end = datetime.fromisoformat(self.end_at)
        minutes = int((end - start).total_seconds() // 60)
        if minutes <= 0:
            raise ValueError("lesson end must be after start")
        return minutes


@dataclass(frozen=True)
class LessonChange:
    external_lesson_id: str
    change_type: str
    changed_fields: dict[str, object]


def _event_hash(
    source: str,
    external_lesson_id: str,
    revision: int,
    change_type: str,
    changed_fields_json: str,
) -> str:
    payload = "\x1f".join(
        (source, external_lesson_id, str(revision), change_type, changed_fields_json)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _record_change(
    connection: sqlite3.Connection,
    *,
    lesson_id: int,
    external_lesson_id: str,
    import_run_id: int,
    revision: int,
    change_type: str,
    changed_fields: dict[str, object],
    created_at: str,
) -> LessonChange:
    changed_fields_json = json.dumps(
        changed_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    connection.execute(
        "INSERT INTO lesson_changes "
        "(lesson_id, import_run_id, change_type, changed_fields_json, event_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            lesson_id,
            import_run_id,
            change_type,
            changed_fields_json,
            _event_hash(
                source=connection.execute(
                    "SELECT source FROM lessons WHERE id = ?", (lesson_id,)
                ).fetchone()[0],
                external_lesson_id=external_lesson_id,
                revision=revision,
                change_type=change_type,
                changed_fields_json=changed_fields_json,
            ),
            created_at,
        ),
    )
    return LessonChange(external_lesson_id, change_type, changed_fields)


def reconcile_snapshot(
    connection: sqlite3.Connection,
    source: str,
    lessons: list[LessonSnapshot],
    *,
    complete: bool,
) -> list[LessonChange]:
    incoming = {lesson.external_lesson_id: lesson for lesson in lessons}
    if len(incoming) != len(lessons):
        raise ValueError("snapshot contains duplicate external lesson ids")

    now = datetime.now(timezone.utc).isoformat()
    changes: list[LessonChange] = []
    with connection:
        cursor = connection.execute(
            "INSERT INTO import_runs "
            "(source, started_at, status, is_complete_snapshot) "
            "VALUES (?, ?, 'running', ?)",
            (source, now, int(complete)),
        )
        import_run_id = cursor.lastrowid
        rows = connection.execute(
            "SELECT id, external_lesson_id, external_group_id, group_name, "
            "start_at, end_at, duration_minutes, status, revision, deleted_at "
            "FROM lessons WHERE source = ?",
            (source,),
        ).fetchall()
        existing = {row[1]: row for row in rows}

        for external_id, lesson in incoming.items():
            row = existing.get(external_id)
            values = {
                "external_group_id": lesson.external_group_id,
                "group_name": lesson.group_name,
                "start_at": lesson.start_at,
                "end_at": lesson.end_at,
                "duration_minutes": lesson.duration_minutes,
                "status": lesson.status,
                "deleted_at": None,
            }
            if row is None:
                inserted = connection.execute(
                    "INSERT INTO lessons "
                    "(source, external_lesson_id, external_group_id, group_name, start_at, end_at, duration_minutes, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        source,
                        external_id,
                        lesson.external_group_id,
                        lesson.group_name,
                        lesson.start_at,
                        lesson.end_at,
                        lesson.duration_minutes,
                        lesson.status,
                    ),
                )
                changes.append(
                    _record_change(
                        connection,
                        lesson_id=inserted.lastrowid,
                        external_lesson_id=external_id,
                        import_run_id=import_run_id,
                        revision=1,
                        change_type="new",
                        changed_fields=values,
                        created_at=now,
                    )
                )
                continue

            columns = (
                "external_group_id",
                "group_name",
                "start_at",
                "end_at",
                "duration_minutes",
                "status",
                "deleted_at",
            )
            old_values = dict(zip(columns, row[2:8] + (row[9],)))
            changed_fields = {
                name: {"old": old_values[name], "new": values[name]}
                for name in columns
                if old_values[name] != values[name]
            }
            if not changed_fields:
                continue

            revision = row[8] + 1
            connection.execute(
                "UPDATE lessons SET external_group_id = ?, group_name = ?, "
                "start_at = ?, end_at = ?, duration_minutes = ?, status = ?, "
                "revision = ?, deleted_at = NULL WHERE id = ?",
                (
                    lesson.external_group_id,
                    lesson.group_name,
                    lesson.start_at,
                    lesson.end_at,
                    lesson.duration_minutes,
                    lesson.status,
                    revision,
                    row[0],
                ),
            )
            changes.append(
                _record_change(
                    connection,
                    lesson_id=row[0],
                    external_lesson_id=external_id,
                    import_run_id=import_run_id,
                    revision=revision,
                    change_type="changed",
                    changed_fields=changed_fields,
                    created_at=now,
                )
            )

        if complete:
            for external_id, row in existing.items():
                if external_id in incoming or row[9] is not None:
                    continue
                revision = row[8] + 1
                connection.execute(
                    "UPDATE lessons SET revision = ?, deleted_at = ? WHERE id = ?",
                    (revision, now, row[0]),
                )
                changes.append(
                    _record_change(
                        connection,
                        lesson_id=row[0],
                        external_lesson_id=external_id,
                        import_run_id=import_run_id,
                        revision=revision,
                        change_type="deleted",
                        changed_fields={"deleted_at": {"old": None, "new": now}},
                        created_at=now,
                    )
                )

        connection.execute(
            "UPDATE import_runs SET completed_at = ?, status = 'completed' WHERE id = ?",
            (now, import_run_id),
        )
    return changes
