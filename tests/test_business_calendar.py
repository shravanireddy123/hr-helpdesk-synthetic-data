from datetime import datetime

from hrgen.business_calendar import (
    add_business_minutes,
    business_minutes_between,
    is_business_day,
    roll_forward,
)
from datetime import date


def test_friday_evening_rolls_to_monday():
    # Fri 5 Jun 2026 17:00 + 120 min: 60 left on Friday, 60 on Monday.
    assert add_business_minutes(datetime(2026, 6, 5, 17, 0), 120) == datetime(2026, 6, 8, 10, 30)


def test_start_after_closing_rolls_to_next_morning():
    start = datetime(2026, 6, 9, 20, 0)  # Tuesday 20:00
    assert roll_forward(start) == datetime(2026, 6, 10, 9, 30)
    assert add_business_minutes(start, 60) == datetime(2026, 6, 10, 10, 30)


def test_start_before_opening():
    assert add_business_minutes(datetime(2026, 6, 8, 8, 0), 30) == datetime(2026, 6, 8, 10, 0)


def test_holiday_and_weekend_are_skipped():
    # Thu 1 Oct 17:30 + 60: 30 on Thursday, Fri 2 Oct is a holiday, then a weekend,
    # so the remaining 30 land on Mon 5 Oct.
    assert not is_business_day(date(2026, 10, 2))
    assert add_business_minutes(datetime(2026, 10, 1, 17, 30), 60) == datetime(2026, 10, 5, 10, 0)


def test_between_same_day():
    assert business_minutes_between(datetime(2026, 6, 9, 10, 0), datetime(2026, 6, 9, 12, 30)) == 150


def test_between_across_weekend():
    assert business_minutes_between(datetime(2026, 6, 5, 17, 0), datetime(2026, 6, 8, 10, 30)) == 120


def test_between_full_business_day():
    assert business_minutes_between(datetime(2026, 6, 8, 9, 30), datetime(2026, 6, 9, 9, 30)) == 510


def test_add_and_between_are_consistent():
    for start in (datetime(2026, 6, 5, 17, 0), datetime(2026, 6, 6, 12, 0), datetime(2026, 10, 1, 17, 30)):
        for minutes in (0, 45, 510, 1500):
            end = add_business_minutes(start, minutes)
            assert business_minutes_between(roll_forward(start), end) == minutes