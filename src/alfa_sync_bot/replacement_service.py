from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .availability import Offer, TimeInterval, YEKATERINBURG, assess_offers
from .replacement_parser import MessageEntity, parse_replacement_message


class ResultCategory(str, Enum):
    AVAILABLE = "available"
    CONDITIONAL = "conditional"
    SHIFTABLE = "shiftable"
    UNAVAILABLE = "unavailable"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class AnalyzedOffer:
    name: str
    start: datetime
    end: datetime
    category: ResultCategory
    conflicts_with: tuple[str, ...] = ()
    shift_minutes: tuple[int, ...] = ()


def analyze_message(
    text: str,
    scheduled: list[TimeInterval],
    entities: tuple[MessageEntity, ...] = (),
) -> list[AnalyzedOffer]:
    parsed = parse_replacement_message(text, entities=entities)
    valid = []
    for index, offer in enumerate(parsed.offers):
        if offer.duration_matches:
            valid.append(
                Offer(
                    key=str(index),
                    name=offer.name,
                    interval=TimeInterval(
                        start=offer.start.astimezone(YEKATERINBURG),
                        end=offer.end.astimezone(YEKATERINBURG),
                    ),
                )
            )

    assessed = {
        assessment.offer.key: assessment
        for assessment in assess_offers(valid, scheduled)
    }
    results = []
    for index, offer in enumerate(parsed.offers):
        start = offer.start.astimezone(YEKATERINBURG)
        end = offer.end.astimezone(YEKATERINBURG)
        if not offer.duration_matches:
            results.append(
                AnalyzedOffer(
                    name=offer.name,
                    start=start,
                    end=end,
                    category=ResultCategory.REVIEW_REQUIRED,
                )
            )
            continue

        assessment = assessed[str(index)]
        results.append(
            AnalyzedOffer(
                name=offer.name,
                start=start,
                end=end,
                category=ResultCategory(assessment.status.value),
                conflicts_with=tuple(
                    parsed.offers[int(key)].name
                    for key in assessment.conflicts_with
                ),
                shift_minutes=assessment.shift_minutes,
            )
        )
    return results
