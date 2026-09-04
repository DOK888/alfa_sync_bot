from datetime import timedelta

from .replacement_service import AnalyzedOffer
from .replacement_service import ResultCategory


def _time_range(start, end) -> str:
    return f"{start:%H:%M}–{end:%H:%M} ЕКБ"


def render_analysis(items: list[AnalyzedOffer]) -> str:
    sections = []

    available = [item for item in items if item.category == ResultCategory.AVAILABLE]
    if available:
        lines = ["✅ Можно взять"]
        lines.extend(
            f"• {item.name} — {_time_range(item.start, item.end)}"
            for item in available
        )
        sections.append("\n".join(lines))

    conditional = [
        item for item in items if item.category == ResultCategory.CONDITIONAL
    ]
    if conditional:
        lines = ["🔀 Можно, если не брать другое предложение"]
        lines.extend(
            f"• {item.name} — если не брать: {', '.join(item.conflicts_with)}"
            for item in conditional
        )
        sections.append("\n".join(lines))

    shiftable = [item for item in items if item.category == ResultCategory.SHIFTABLE]
    if shiftable:
        lines = ["🕒 Можно со сдвигом до 30 минут"]
        for item in shiftable:
            for minutes in item.shift_minutes:
                delta = timedelta(minutes=minutes)
                prefix = f"{minutes:+d} мин"
                lines.append(
                    f"• {item.name} — {prefix} → "
                    f"{_time_range(item.start + delta, item.end + delta)}"
                )
        sections.append("\n".join(lines))

    unavailable = [
        item for item in items if item.category == ResultCategory.UNAVAILABLE
    ]
    if unavailable:
        lines = ["❌ Нельзя взять"]
        lines.extend(
            f"• {item.name} — {_time_range(item.start, item.end)}"
            for item in unavailable
        )
        sections.append("\n".join(lines))

    review = [
        item for item in items if item.category == ResultCategory.REVIEW_REQUIRED
    ]
    if review:
        lines = ["⚠️ Требует проверки"]
        lines.extend(
            f"• {item.name} — {_time_range(item.start, item.end)}"
            for item in review
        )
        sections.append("\n".join(lines))

    return "\n\n".join(sections)
