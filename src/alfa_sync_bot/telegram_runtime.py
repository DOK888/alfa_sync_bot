from collections.abc import Iterable
from datetime import date, datetime
from typing import Any, Protocol
import sqlite3
from zoneinfo import ZoneInfo

from .database import get_runtime_state, set_runtime_state
from .access import owner_id, is_owner_message
from .finance_view import render_finance
from .gemini_fallback import should_use_fallback
from .message_service import analyze_replacement_text
from .notifications import deliver_pending_notifications, register_chat
from .replacement_parser import (
    MessageEntity,
    parse_replacement_message,
    text_without_struck_entities,
)
from .schedule_view import render_schedule
from .shadow import request_import


STATE_KEY = "telegram.next_update_id"
YEKATERINBURG = ZoneInfo("Asia/Yekaterinburg")
MENU = {
    "keyboard": [
        ["📅 На сегодня", "🗓 На неделю"],
        ["💰 Мои финансы", "📝 Написать отчет"],
        ["⚙️ Настройки ИИ"],
        ["🔄 Собрать данные сейчас"],
    ],
    "resize_keyboard": True,
}


class TelegramClient(Protocol):
    def get_updates(self, offset: int | None) -> Iterable[dict]: ...

    def send_message(
        self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> None: ...


class ReplacementFallback(Protocol):
    def canonicalize(self, text: str, reference_date: date | None) -> str | None: ...


def _message_entities(message: dict) -> tuple[MessageEntity, ...]:
    return tuple(
        MessageEntity(
            kind=entity["type"],
            offset=entity["offset"],
            length=entity["length"],
            url=entity.get("url"),
        )
        for entity in message.get("entities", [])
        if all(field in entity for field in ("type", "offset", "length"))
    )


def message_reference_date(message: dict) -> date | None:
    timestamp = message.get("date")
    if not isinstance(timestamp, int):
        return None
    return datetime.fromtimestamp(timestamp, tz=YEKATERINBURG).date()


def process_updates(
    client: TelegramClient,
    connection: sqlite3.Connection,
    *,
    fallback: ReplacementFallback | None = None,
) -> int | None:
    owner = owner_id()
    stored_offset = get_runtime_state(connection, STATE_KEY)
    offset = int(stored_offset) if stored_offset is not None else None
    next_offset = offset

    for update in client.get_updates(offset):
        update_id = update.get("update_id")
        if not isinstance(update_id, int):
            continue

        message = update.get("message")
        if not is_owner_message(message, owner):
            next_offset = max(next_offset or 0, update_id + 1)
            continue
        if isinstance(message, dict):
            text = message.get("text")
            chat = message.get("chat")
            if isinstance(text, str) and isinstance(chat, dict):
                chat_id = chat.get("id")
                if isinstance(chat_id, int) and text in ("/start", "Меню"):
                    register_chat(connection, chat_id)
                    client.send_message(
                        chat_id,
                        "Готов. Выбери действие в меню.",
                        reply_markup=MENU,
                    )
                    candidate_offset = update_id + 1
                    if next_offset is None or candidate_offset > next_offset:
                        next_offset = candidate_offset
                    continue
                entities = _message_entities(message)
                reference_date = message_reference_date(message)
                menu_day = reference_date or datetime.now(tz=YEKATERINBURG).date()
                if isinstance(chat_id, int) and text == "📅 На сегодня":
                    client.send_message(
                        chat_id, render_schedule(connection, menu_day, menu_day)
                    )
                    candidate_offset = update_id + 1
                    if next_offset is None or candidate_offset > next_offset:
                        next_offset = candidate_offset
                    continue
                if isinstance(chat_id, int) and text == "🗓 На неделю":
                    week_start = menu_day.fromordinal(menu_day.toordinal() - menu_day.weekday())
                    week_end = week_start.fromordinal(week_start.toordinal() + 6)
                    client.send_message(
                        chat_id, render_schedule(connection, week_start, week_end)
                    )
                    candidate_offset = update_id + 1
                    if next_offset is None or candidate_offset > next_offset:
                        next_offset = candidate_offset
                    continue
                if isinstance(chat_id, int) and text == "💰 Мои финансы":
                    client.send_message(chat_id, render_finance(connection, menu_day))
                    candidate_offset = update_id + 1
                    if next_offset is None or candidate_offset > next_offset:
                        next_offset = candidate_offset
                    continue
                if isinstance(chat_id, int) and text == "📝 Написать отчет":
                    client.send_message(
                        chat_id,
                        "Отчёт: автоматическая отправка из старой версии ещё не подключена. "
                        "Расписание и финансы доступны в меню.",
                    )
                    candidate_offset = update_id + 1
                    if next_offset is None or candidate_offset > next_offset:
                        next_offset = candidate_offset
                    continue
                if isinstance(chat_id, int) and text == "⚙️ Настройки ИИ":
                    client.send_message(
                        chat_id,
                        "ИИ используется только как запасной разборщик замен и не меняет расписание.",
                    )
                    candidate_offset = update_id + 1
                    if next_offset is None or candidate_offset > next_offset:
                        next_offset = candidate_offset
                    continue
                if isinstance(chat_id, int) and text == "🔄 Собрать данные сейчас":
                    request_import(connection)
                    client.send_message(
                        chat_id,
                        "Запрос принят. Импорт запустится при ближайшей безопасной проверке источника.",
                    )
                    candidate_offset = update_id + 1
                    if next_offset is None or candidate_offset > next_offset:
                        next_offset = candidate_offset
                    continue
                parsed = parse_replacement_message(
                    text, entities, reference_date=reference_date
                )
                analysis_text = text
                analysis_entities = entities
                if (
                    fallback
                    and should_use_fallback(text)
                    and (not parsed.offers or parsed.unresolved_offer_count)
                ):
                    canonical = fallback.canonicalize(
                        text_without_struck_entities(text, entities), reference_date
                    )
                    if canonical:
                        analysis_text = canonical
                        analysis_entities = ()
                        parsed = parse_replacement_message(
                            canonical, reference_date=reference_date
                        )
                if isinstance(chat_id, int) and (
                    parsed.offers or parsed.unresolved_offer_count
                ):
                    client.send_message(
                        chat_id,
                        analyze_replacement_text(
                            analysis_text,
                            connection,
                            analysis_entities,
                            reference_date=reference_date,
                        ),
                    )

        candidate_offset = update_id + 1
        if next_offset is None or candidate_offset > next_offset:
            next_offset = candidate_offset

    if next_offset is not None:
        set_runtime_state(connection, STATE_KEY, str(next_offset))
        connection.commit()
    deliver_pending_notifications(connection, client.send_message)
    return next_offset
