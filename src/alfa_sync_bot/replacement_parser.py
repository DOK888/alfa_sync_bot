from dataclasses import dataclass
from datetime import date, datetime
import re
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo


MOSCOW = ZoneInfo("Europe/Moscow")
DATE_LINE = re.compile(
    r"^(?P<date>\d{2}\.\d{2}\.\d{4})(?:\s+(?P<kind>.*?))?\s*$"
)
RUSSIAN_DATE_LINE = re.compile(
    r"^(?P<day>\d{1,2})\s+(?P<month>января|февраля|марта|апреля|мая|июня|"
    r"июля|августа|сентября|октября|ноября|декабря)(?:\s+(?P<kind>.*?))?\s*$",
    re.IGNORECASE,
)
SHORT_DATE_LINE = re.compile(
    r"^(?P<kind>.*?\bс\s+)(?P<date>\d{1,2}\.\d{2})(?:\s+(?P<tail>.*?))?\s*$",
    re.IGNORECASE,
)
BARE_SHORT_DATE_LINE = re.compile(
    r"^(?P<date>\d{1,2}\.\d{2})(?:\s+(?P<kind>.*?))?\s*$"
)
RELATIVE_DATE_LINE = re.compile(r"\b(?P<relative>сегодня|завтра)\b", re.IGNORECASE)
OFFER_LINE = re.compile(
    r"^(?P<name>.+?)\s*\((?P<duration>\d+)\s*минут[а-я]*\)\s*"
    r"(?:с\s*)?(?P<start>\d{1,2}:\d{2})\s*(?:—|–|-|до)\s*"
    r"(?P<end>\d{1,2}:\d{2})\s*$",
    re.IGNORECASE,
)
OFFER_TITLE_LINE = re.compile(
    r"^(?P<name>.+?)\s*\((?P<duration>\d+)\s*минут[а-я]*\)\s*$",
    re.IGNORECASE,
)
TIME_LINE = re.compile(
    r"^(?:с\s*)?(?P<start>\d{1,2}:\d{2})\s*(?:—|–|-|до)\s*"
    r"(?P<end>\d{1,2}:\d{2})\s*$",
    re.IGNORECASE,
)

RUSSIAN_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


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
    unresolved_offer_count: int = 0


def _utf16_offset_to_index(text: str, offset: int) -> int:
    if offset <= 0:
        return 0
    units = 0
    for index, character in enumerate(text):
        units += len(character.encode("utf-16-le")) // 2
        if units >= offset:
            return index + 1
    return len(text)


def _telegram_entities_to_python_indices(
    text: str, entities: tuple[MessageEntity, ...]
) -> tuple[MessageEntity, ...]:
    converted = []
    for entity in entities:
        start = _utf16_offset_to_index(text, entity.offset)
        end = _utf16_offset_to_index(text, entity.offset + entity.length)
        converted.append(
            MessageEntity(
                kind=entity.kind,
                offset=start,
                length=end - start,
                url=entity.url,
            )
        )
    return tuple(converted)


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
    text: str,
    entities: tuple[MessageEntity, ...] = (),
    *,
    reference_year: int | None = None,
    reference_date: date | None = None,
) -> ParsedMessage:
    entities = _telegram_entities_to_python_indices(text, entities)
    text = _without_struck_text(text, entities)
    current_date: date | None = None
    if reference_date is None:
        reference_date = datetime.now(MOSCOW).date()
    if reference_year is None:
        reference_year = reference_date.year
    replacement_type = ""
    offers = []
    unresolved_offer_count = 0
    pending_offer: tuple[re.Match[str], int, int] | None = None

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
            pending_offer = None
            current_date = datetime.strptime(
                date_match.group("date"), "%d.%m.%Y"
            ).date()
            replacement_type = (date_match.group("kind") or "").strip()
            continue

        russian_date_match = RUSSIAN_DATE_LINE.match(line)
        if russian_date_match:
            pending_offer = None
            current_date = date(
                reference_year,
                RUSSIAN_MONTHS[russian_date_match.group("month").lower()],
                int(russian_date_match.group("day")),
            )
            replacement_type = (russian_date_match.group("kind") or "").strip()
            continue

        short_date_match = SHORT_DATE_LINE.match(line)
        if short_date_match:
            pending_offer = None
            current_date = datetime.strptime(
                f"{short_date_match.group('date')}.{reference_year}", "%d.%m.%Y"
            ).date()
            replacement_type = line
            continue

        bare_short_date_match = BARE_SHORT_DATE_LINE.match(line)
        if bare_short_date_match:
            pending_offer = None
            current_date = datetime.strptime(
                f"{bare_short_date_match.group('date')}.{reference_year}",
                "%d.%m.%Y",
            ).date()
            replacement_type = (bare_short_date_match.group("kind") or "").strip()
            continue

        relative_date_match = RELATIVE_DATE_LINE.search(line)
        if relative_date_match:
            pending_offer = None
            current_date = reference_date
            if relative_date_match.group("relative").lower() == "завтра":
                current_date = current_date.fromordinal(current_date.toordinal() + 1)
            replacement_type = line
            continue

        if pending_offer is not None:
            time_match = TIME_LINE.match(line)
            if time_match:
                offer_match, title_offset, title_leading_space = pending_offer
                if current_date is None:
                    unresolved_offer_count += 1
                else:
                    start_time = datetime.strptime(
                        time_match.group("start"), "%H:%M"
                    ).time()
                    end_time = datetime.strptime(
                        time_match.group("end"), "%H:%M"
                    ).time()
                    name_start = (
                        title_offset + title_leading_space + offer_match.start("name")
                    )
                    name_end = (
                        title_offset + title_leading_space + offer_match.end("name")
                    )
                    offers.append(
                        ParsedOffer(
                            name=offer_match.group("name").strip(),
                            replacement_type=replacement_type,
                            start=datetime.combine(
                                current_date, start_time, tzinfo=MOSCOW
                            ),
                            end=datetime.combine(current_date, end_time, tzinfo=MOSCOW),
                            declared_duration_minutes=int(
                                offer_match.group("duration")
                            ),
                            external_group_id=_group_id_for_span(
                                entities, name_start, name_end
                            ),
                        )
                    )
                pending_offer = None
                continue
            pending_offer = None

        offer_match = OFFER_LINE.match(line)
        if not offer_match:
            title_match = OFFER_TITLE_LINE.match(line)
            if title_match:
                pending_offer = (title_match, line_offset, leading_space)
            continue
        if current_date is None:
            unresolved_offer_count += 1
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

    return ParsedMessage(
        offers=tuple(offers), unresolved_offer_count=unresolved_offer_count
    )
