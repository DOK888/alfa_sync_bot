from datetime import date, datetime
import sqlite3

from .availability import TimeInterval
from .rendering import render_analysis
from .replacement_parser import MessageEntity, parse_replacement_message
from .replacement_service import analyze_message


def load_active_intervals(connection: sqlite3.Connection) -> list[TimeInterval]:
    rows = connection.execute(
        "SELECT start_at, end_at FROM lessons "
        "WHERE deleted_at IS NULL AND status IN ('planned', 'conducted')"
    )
    return [
        TimeInterval(
            start=datetime.fromisoformat(start_at),
            end=datetime.fromisoformat(end_at),
        )
        for start_at, end_at in rows
    ]


def analyze_replacement_text(
    text: str,
    connection: sqlite3.Connection,
    entities: tuple[MessageEntity, ...] = (),
    *,
    reference_date: date | None = None,
) -> str:
    parsed = parse_replacement_message(
        text, entities, reference_date=reference_date
    )
    if not parsed.offers and parsed.unresolved_offer_count:
        return (
            "Нашёл предложение замены, но не смог определить дату. "
            "Пришли строку с датой или уточни, это сегодня или завтра."
        )
    if not parsed.offers:
        return "Не нашёл предложений замены в сообщении."
    items = analyze_message(
        text,
        load_active_intervals(connection),
        entities,
        reference_date=reference_date,
    )
    return render_analysis(items)
