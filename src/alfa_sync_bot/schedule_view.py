from datetime import date, datetime
import sqlite3


def render_schedule(
    connection: sqlite3.Connection, start_day: date, end_day: date
) -> str:
    rows = connection.execute(
        "SELECT group_name, start_at, end_at, source, status FROM lessons "
        "WHERE deleted_at IS NULL AND status != 'cancelled' "
        "AND substr(start_at, 1, 10) BETWEEN ? AND ? "
        "ORDER BY start_at, group_name COLLATE NOCASE",
        (start_day.isoformat(), end_day.isoformat()),
    ).fetchall()
    title = (
        f"📅 Расписание на {start_day:%d.%m.%Y}"
        if start_day == end_day
        else f"🗓 Расписание на неделю {start_day:%d.%m.%Y}–{end_day:%d.%m.%Y}"
    )
    lines = [title, "🕒 Время Екатеринбурга", ""]
    if not rows:
        return "\n".join(lines + ["На этот период уроков нет."])

    last_day = None
    for number, (group_name, start_at, end_at, source, status) in enumerate(rows, 1):
        start = datetime.fromisoformat(start_at)
        end = datetime.fromisoformat(end_at)
        if start_day != end_day and start.date() != last_day:
            if last_day is not None:
                lines.append("")
            weekday = ("Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье")[start.weekday()]
            lines.append(f"📆 {weekday}, {start:%d.%m}")
            last_day = start.date()
        school = {"legacy:tetrika": "🟣 Тетрика", "legacy:wellkid": "🟠 WellKid"}.get(source, "🏫 Школа")
        marker = "✅ Проведён" if status == "conducted" else "⏳ Запланирован"
        lines.append(f"{number}. {group_name} — {start:%H:%M}–{end:%H:%M} ЕКБ")
        lines.append(f"   {school} · {marker}")
    lines.extend(["", f"Всего уроков: {len(rows)}"])
    return "\n".join(lines)
