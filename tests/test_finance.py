import unittest
from datetime import date

from alfa_sync_bot.finance import previous_month_bounds, week_bounds


class FinanceTests(unittest.TestCase):
    def test_week_runs_from_monday_through_sunday(self):
        start, end = week_bounds(date(2026, 9, 3))

        self.assertEqual(start, date(2026, 8, 31))
        self.assertEqual(end, date(2026, 9, 6))

    def test_previous_month_bounds_cross_year_boundary(self):
        start, end = previous_month_bounds(date(2026, 1, 15))

        self.assertEqual(start, date(2025, 12, 1))
        self.assertEqual(end, date(2025, 12, 31))


if __name__ == "__main__":
    unittest.main()
