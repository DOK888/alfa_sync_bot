from datetime import date, timedelta
import sqlite3

from .finance import income_overview, week_bounds, previous_month_bounds


def _rubles(amount_minor: int) -> str:
    return f"{amount_minor // 100:,}".replace(",", " ") + " ₽"


def render_finance(connection: sqlite3.Connection, today: date) -> str:
    overview = income_overview(connection, today)
    previous_start, previous_end = previous_month_bounds(today)
    week_start, week_end = week_bounds(today)
    lines = [
        f"💰 Финансовая сводка на {today:%d.%m.%Y}",
        "",
        "✅ Заработано по проведённым урокам",
        f"Прошлый месяц: {_rubles(overview.previous_month_earned_minor)}",
        f"   {previous_start:%d.%m.%Y}–{previous_end:%d.%m.%Y}",
        f"Эта неделя: {_rubles(overview.current_week_earned_minor)}",
        f"   {week_start:%d.%m.%Y}–{week_end:%d.%m.%Y}",
        "",
    ]
    if overview.future_weeks_planned_minor:
        lines.append("📈 Ожидается по будущим неделям")
        for week_start, amount_minor in overview.future_weeks_planned_minor:
            week_end = week_start + timedelta(days=6)
            lines.append(
                f"• {week_start:%d.%m}–{week_end:%d.%m}: {_rubles(amount_minor)}"
            )
    else:
        lines.append("Будущих запланированных уроков нет.")
    lines.extend(["", "Неделя: пн–вс. Начислено ≠ выплачено.", "Прогноз зависит от назначенных уроков в базе."])
    return "\n".join(lines)
