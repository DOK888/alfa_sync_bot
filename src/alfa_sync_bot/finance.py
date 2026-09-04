from dataclasses import dataclass
from datetime import date, datetime, timedelta
import sqlite3


def week_bounds(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def previous_month_bounds(day: date) -> tuple[date, date]:
    first_current = day.replace(day=1)
    last_previous = first_current - timedelta(days=1)
    return last_previous.replace(day=1), last_previous


@dataclass(frozen=True)
class IncomeOverview:
    previous_month_earned_minor: int
    current_week_earned_minor: int
    future_weeks_planned_minor: tuple[tuple[date, int], ...]


def income_overview(
    connection: sqlite3.Connection, today: date
) -> IncomeOverview:
    previous_start, previous_end = previous_month_bounds(today)
    current_start, current_end = week_bounds(today)
    previous_total = 0
    current_total = 0
    future: dict[date, int] = {}

    rows = connection.execute(
        "SELECT income_accruals.amount_minor, income_accruals.status, "
        "income_accruals.earned_at, lessons.start_at "
        "FROM income_accruals JOIN lessons ON lessons.id = income_accruals.lesson_id"
    )
    for amount_minor, status, earned_at, lesson_start_at in rows:
        if status in ("earned", "paid") and earned_at:
            earned_date = datetime.fromisoformat(earned_at).date()
            if previous_start <= earned_date <= previous_end:
                previous_total += amount_minor
            if current_start <= earned_date <= current_end:
                current_total += amount_minor
        if status == "planned":
            lesson_date = datetime.fromisoformat(lesson_start_at).date()
            if lesson_date > current_end:
                future_start, _ = week_bounds(lesson_date)
                future[future_start] = future.get(future_start, 0) + amount_minor

    return IncomeOverview(
        previous_month_earned_minor=previous_total,
        current_week_earned_minor=current_total,
        future_weeks_planned_minor=tuple(sorted(future.items())),
    )
