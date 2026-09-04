from collections.abc import Iterable
from datetime import date, datetime
from typing import Protocol
import sqlite3
from zoneinfo import ZoneInfo

from .database import get_runtime_state, set_runtime_state
from .message_service import analyze_replacement_text
from .replacement_parser import MessageEntity, parse_replacement_message


STATE_KEY = "telegram.next_update_id"
YEKATERINBURG = ZoneInfo("Asia/Yekaterinburg")


class TelegramClient(Protocol):
    def get_updates(self, offset: int | None) -> Iterable[dict]: ...

    def send_message(self, chat_id: int, text: str) -> None: ...


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
    client: TelegramClient, connection: sqlite3.Connection
) -> int | None:
    stored_offset = get_runtime_state(connection, STATE_KEY)
    offset = int(stored_offset) if stored_offset is not None else None
    next_offset = offset

    for update in client.get_updates(offset):
        update_id = update.get("update_id")
        if not isinstance(update_id, int):
            continue

        message = update.get("message")
        if isinstance(message, dict):
            text = message.get("text")
            chat = message.get("chat")
            if isinstance(text, str) and isinstance(chat, dict):
                chat_id = chat.get("id")
                entities = _message_entities(message)
                parsed = parse_replacement_message(
                    text, entities, reference_date=message_reference_date(message)
                )
                if isinstance(chat_id, int) and (
                    parsed.offers or parsed.unresolved_offer_count
                ):
                    client.send_message(
                        chat_id,
                        analyze_replacement_text(
                            text,
                            connection,
                            entities,
                            reference_date=message_reference_date(message),
                        ),
                    )

        candidate_offset = update_id + 1
        if next_offset is None or candidate_offset > next_offset:
            next_offset = candidate_offset

    if next_offset is not None:
        set_runtime_state(connection, STATE_KEY, str(next_offset))
        connection.commit()
    return next_offset
