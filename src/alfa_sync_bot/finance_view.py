from datetime import date
import sqlite3

from .finance import income_overview


def _rubles(amount_minor: int) -> str:
    return f"{amount_minor // 100:,}".replace(",", " ") + " ₽"


def render_finance(connection: sqlite3.Connection, today: date) -> str:
    overview = income_overview(connection, today)
    lines = [
        "Финансы",
        f"Прошлый месяц: {_rubles(overview.previous_month_earned_minor)}",
        f"Эта неделя: {_rubles(overview.current_week_earned_minor)}",
    ]
    if overview.future_weeks_planned_minor:
        lines.append("Будущие недели:")
        for week_start, amount_minor in overview.future_weeks_planned_minor:
            week_end = week_start.fromordinal(week_start.toordinal() + 6)
            lines.append(
                f"{week_start:%d.%m}–{week_end:%d.%m}: {_rubles(amount_minor)}"
            )
    else:
        lines.append("Будущих запланированных уроков нет.")
    return "\n".join(lines)
