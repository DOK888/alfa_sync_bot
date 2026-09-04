import unittest
from datetime import datetime

from alfa_sync_bot.availability import (
    AvailabilityStatus,
    Offer,
    TimeInterval,
    assess_offers,
    to_yekaterinburg,
)


class AvailabilityTests(unittest.TestCase):
    def test_converts_moscow_offer_time_to_yekaterinburg(self):
        moscow_time = datetime(2026, 9, 5, 12, 30)

        result = to_yekaterinburg(moscow_time)

        self.assertEqual(result.isoformat(), "2026-09-05T14:30:00+05:00")

    def test_adjacent_intervals_do_not_overlap(self):
        first = TimeInterval(
            start=datetime(2026, 9, 5, 14, 0),
            end=datetime(2026, 9, 5, 15, 0),
        )
        second = TimeInterval(
            start=datetime(2026, 9, 5, 15, 0),
            end=datetime(2026, 9, 5, 16, 0),
        )

        self.assertFalse(first.overlaps(second))

    def test_offer_without_schedule_conflicts_is_available(self):
        offer = Offer(
            key="group-1",
            name="Group 1",
            interval=TimeInterval(
                start=datetime(2026, 9, 5, 14, 0),
                end=datetime(2026, 9, 5, 15, 0),
            ),
        )

        result = assess_offers([offer], scheduled=[])

        self.assertEqual(result[0].status, AvailabilityStatus.AVAILABLE)

    def test_overlapping_free_offers_are_conditional_alternatives(self):
        first = Offer(
            key="group-1",
            name="Group 1",
            interval=TimeInterval(
                start=datetime(2026, 9, 5, 14, 0),
                end=datetime(2026, 9, 5, 15, 30),
            ),
        )
        second = Offer(
            key="group-2",
            name="Group 2",
            interval=TimeInterval(
                start=datetime(2026, 9, 5, 15, 10),
                end=datetime(2026, 9, 5, 16, 10),
            ),
        )

        result = assess_offers([first, second], scheduled=[])

        self.assertEqual(result[0].status, AvailabilityStatus.CONDITIONAL)
        self.assertEqual(result[0].conflicts_with, ("group-2",))
        self.assertEqual(result[1].status, AvailabilityStatus.CONDITIONAL)
        self.assertEqual(result[1].conflicts_with, ("group-1",))

    def test_conflicting_offer_is_shiftable_to_nearest_free_time(self):
        offer = Offer(
            key="group-1",
            name="Group 1",
            interval=TimeInterval(
                start=datetime(2026, 9, 5, 14, 30),
                end=datetime(2026, 9, 5, 15, 30),
            ),
        )
        scheduled = [
            TimeInterval(
                start=datetime(2026, 9, 5, 14, 0),
                end=datetime(2026, 9, 5, 15, 0),
            )
        ]

        result = assess_offers([offer], scheduled=scheduled)

        self.assertEqual(result[0].status, AvailabilityStatus.SHIFTABLE)
        self.assertEqual(result[0].shift_minutes, (30,))


if __name__ == "__main__":
    unittest.main()
