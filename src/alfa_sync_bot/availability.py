from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


MOSCOW = ZoneInfo("Europe/Moscow")
YEKATERINBURG = ZoneInfo("Asia/Yekaterinburg")


@dataclass(frozen=True)
class TimeInterval:
    start: datetime
    end: datetime

    def overlaps(self, other: "TimeInterval") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Offer:
    key: str
    name: str
    interval: TimeInterval


class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    CONDITIONAL = "conditional"
    SHIFTABLE = "shiftable"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Assessment:
    offer: Offer
    status: AvailabilityStatus
    conflicts_with: tuple[str, ...] = ()
    shift_minutes: tuple[int, ...] = ()


def _nearest_free_shifts(
    interval: TimeInterval,
    scheduled: list[TimeInterval],
    limit_minutes: int = 30,
) -> tuple[int, ...]:
    for magnitude in range(1, limit_minutes + 1):
        free = []
        for offset in (-magnitude, magnitude):
            delta = timedelta(minutes=offset)
            shifted = TimeInterval(
                start=interval.start + delta,
                end=interval.end + delta,
            )
            if not any(shifted.overlaps(item) for item in scheduled):
                free.append(offset)
        if free:
            return tuple(free)
    return ()


def assess_offers(
    offers: list[Offer], scheduled: list[TimeInterval]
) -> list[Assessment]:
    assessments = []
    for offer in offers:
        if any(offer.interval.overlaps(item) for item in scheduled):
            shifts = _nearest_free_shifts(offer.interval, scheduled)
            assessments.append(
                Assessment(
                    offer=offer,
                    status=(
                        AvailabilityStatus.SHIFTABLE
                        if shifts
                        else AvailabilityStatus.UNAVAILABLE
                    ),
                    shift_minutes=shifts,
                )
            )
            continue

        conflicts = tuple(
            other.key
            for other in offers
            if other.key != offer.key and offer.interval.overlaps(other.interval)
        )
        status = (
            AvailabilityStatus.CONDITIONAL
            if conflicts
            else AvailabilityStatus.AVAILABLE
        )
        assessments.append(
            Assessment(offer=offer, status=status, conflicts_with=conflicts)
        )
    return assessments


def to_yekaterinburg(moscow_time: datetime) -> datetime:
    return moscow_time.replace(tzinfo=MOSCOW).astimezone(YEKATERINBURG)
