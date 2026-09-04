from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import Any

from .availability import YEKATERINBURG
from .lesson_sync import LessonSnapshot


SCHOOLS = ("tetrika", "wellkid")
STATUS_MAP = {
    "planned": "planned",
    "conducted": "conducted",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}


@dataclass(frozen=True)
class ParsedLegacyReport:
    lessons_by_source: dict[str, list[LessonSnapshot]]
    complete_sources: set[str]
    rejected_lesson_count: int


@dataclass(frozen=True)
class _LegacyLesson:
    school: str
    group_name: str
    duration_minutes: int
    status: str
    start: datetime
    end: datetime


def _parse_lesson(school: str, payload: object) -> _LegacyLesson | None:
    if not isinstance(payload, dict):
        return None
    try:
        date_text = payload["date"]
        start_text = payload["start"]
        end_text = payload["end"]
        group_name = payload["group"]
        duration_minutes = int(payload["duration"])
        status = STATUS_MAP[str(payload["status"]).lower()]
        if not isinstance(date_text, str) or not isinstance(start_text, str):
            return None
        if not isinstance(end_text, str) or not isinstance(group_name, str):
            return None
        if not group_name.strip() or duration_minutes <= 0:
            return None
        start = datetime.strptime(
            f"{date_text} {start_text}", "%d.%m.%Y %H:%M"
        ).replace(tzinfo=YEKATERINBURG)
        end = datetime.strptime(
            f"{date_text} {end_text}", "%d.%m.%Y %H:%M"
        ).replace(tzinfo=YEKATERINBURG)
        if end <= start:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return _LegacyLesson(
        school=school,
        group_name=group_name.strip(),
        duration_minutes=duration_minutes,
        status=status,
        start=start,
        end=end,
    )


def _fallback_id(lesson: _LegacyLesson, occurrence: int) -> str:
    identity = "\x1f".join(
        (
            lesson.school,
            lesson.start.date().isoformat(),
            lesson.group_name.casefold(),
            str(lesson.duration_minutes),
            str(occurrence),
        )
    )
    return "legacy:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def parse_legacy_report(payload: dict[str, object]) -> ParsedLegacyReport:
    lessons_by_source = {f"legacy:{school}": [] for school in SCHOOLS}
    complete_sources: set[str] = set()
    rejected_lesson_count = 0

    for school in SCHOOLS:
        source = f"legacy:{school}"
        section: Any = payload.get(school)
        if not isinstance(section, dict) or not isinstance(
            section.get("lessons"), list
        ):
            continue

        parsed: list[_LegacyLesson] = []
        source_is_complete = True
        for raw_lesson in section["lessons"]:
            lesson = _parse_lesson(school, raw_lesson)
            if lesson is None:
                source_is_complete = False
                rejected_lesson_count += 1
                continue
            parsed.append(lesson)

        parsed.sort(
            key=lambda lesson: (
                lesson.start,
                lesson.group_name.casefold(),
                lesson.duration_minutes,
                lesson.end,
            )
        )
        occurrences: dict[tuple[str, str, int], int] = {}
        for lesson in parsed:
            occurrence_key = (
                lesson.start.date().isoformat(),
                lesson.group_name.casefold(),
                lesson.duration_minutes,
            )
            occurrence = occurrences.get(occurrence_key, 0)
            occurrences[occurrence_key] = occurrence + 1
            lessons_by_source[source].append(
                LessonSnapshot(
                    external_lesson_id=_fallback_id(lesson, occurrence),
                    external_group_id=None,
                    group_name=lesson.group_name,
                    start_at=lesson.start.isoformat(),
                    end_at=lesson.end.isoformat(),
                    status=lesson.status,
                )
            )
        if source_is_complete:
            complete_sources.add(source)

    return ParsedLegacyReport(
        lessons_by_source=lessons_by_source,
        complete_sources=complete_sources,
        rejected_lesson_count=rejected_lesson_count,
    )
