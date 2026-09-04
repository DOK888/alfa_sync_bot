from dataclasses import dataclass
from datetime import date, datetime
import re
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo


MOSCOW = ZoneInfo("Europe/Moscow")
DATE_LINE = re.compile(
    r"^(?P<date>\d{2}\.\d{2}\.\d{4})(?:\s+(?P<kind>.*?))?\s*$"
)
OFFER_LINE = re.compile(
    r"^(?P<name>.+?)\s*\((?P<duration>\d+)\s*минут[а-я]*\)\s*"
    r"(?:с\s*)?(?P<start>\d{1,2}:\d{2})\s*(?:—|–|-|до)\s*"
    r"(?P<end>\d{1,2}:\d{2})\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedOffer:
    name: str
    replacement_type: str
    start: datetime
    end: datetime
    declared_duration_minutes: int
    external_group_id: str | None = None

    @property
    def actual_duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    @property
    def duration_matches(self) -> bool:
        return self.actual_duration_minutes == self.declared_duration_minutes


@dataclass(frozen=True)
class MessageEntity:
    kind: str
    offset: int
    length: int
    url: str | None = None


@dataclass(frozen=True)
class ParsedMessage:
    offers: tuple[ParsedOffer, ...]


def _without_struck_text(
    text: str, entities: tuple[MessageEntity, ...]
) -> str:
    characters = list(text)
    for entity in entities:
        if entity.kind != "strikethrough":
            continue
        end = min(entity.offset + entity.length, len(characters))
        for index in range(max(entity.offset, 0), end):
            if characters[index] not in "\r\n":
                characters[index] = " "
    return "".join(characters)


def _group_id_for_span(
    entities: tuple[MessageEntity, ...], start: int, end: int
) -> str | None:
    for entity in entities:
        entity_end = entity.offset + entity.length
        if (
            entity.kind == "text_link"
            and entity.url
            and entity.offset < end
            and entity_end > start
        ):
            values = parse_qs(urlparse(entity.url).query).get("id")
            if values:
                return values[0]
    return None


def parse_replacement_message(
    text: str, entities: tuple[MessageEntity, ...] = ()
) -> ParsedMessage:
    text = _without_struck_text(text, entities)
    current_date: date | None = None
    replacement_type = ""
    offers = []

    lines_with_offsets = []
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        lines_with_offsets.append((offset, raw_line.rstrip("\r\n")))
        offset += len(raw_line)

    for line_offset, raw_line in lines_with_offsets:
        leading_space = len(raw_line) - len(raw_line.lstrip())
        line = raw_line.strip()
        if not line:
            continue

        date_match = DATE_LINE.match(line)
        if date_match:
            current_date = datetime.strptime(
                date_match.group("date"), "%d.%m.%Y"
            ).date()
            replacement_type = (date_match.group("kind") or "").strip()
            continue

        offer_match = OFFER_LINE.match(line)
        if not offer_match or current_date is None:
            continue

        start_time = datetime.strptime(offer_match.group("start"), "%H:%M").time()
        end_time = datetime.strptime(offer_match.group("end"), "%H:%M").time()
        name_start = line_offset + leading_space + offer_match.start("name")
        name_end = line_offset + leading_space + offer_match.end("name")
        offers.append(
            ParsedOffer(
                name=offer_match.group("name").strip(),
                replacement_type=replacement_type,
                start=datetime.combine(current_date, start_time, tzinfo=MOSCOW),
                end=datetime.combine(current_date, end_time, tzinfo=MOSCOW),
                declared_duration_minutes=int(offer_match.group("duration")),
                external_group_id=_group_id_for_span(
                    entities, name_start, name_end
                ),
            )
        )

    return ParsedMessage(offers=tuple(offers))
