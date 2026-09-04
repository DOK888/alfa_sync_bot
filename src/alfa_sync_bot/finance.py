from datetime import date, timedelta


def week_bounds(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def previous_month_bounds(day: date) -> tuple[date, date]:
    first_current = day.replace(day=1)
    last_previous = first_current - timedelta(days=1)
    return last_previous.replace(day=1), last_previous
