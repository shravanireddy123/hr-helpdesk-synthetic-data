"""Business-hours maths for the HR helpdesk (all times are naive IST).

Business hours: Monday-Friday, 09:30-18:00 (510 minutes/day), excluding
the company holidays listed below.
"""
from datetime import date, datetime, time, timedelta

OPEN_TIME = time(9, 30)
CLOSE_TIME = time(18, 0)

# Company holiday list for the synthetic company (a design choice, not an
# official government list). Fixed once so every run behaves the same.
HOLIDAYS_2026 = frozenset({
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 4),    # Holi
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 1),    # May Day
    date(2026, 9, 14),   # Ganesh Chaturthi
    date(2026, 10, 2),   # Gandhi Jayanti
    date(2026, 10, 20),  # Dussehra
    date(2026, 12, 25),  # Christmas
})


def is_business_day(d: date) -> bool:
    """True for Mon-Fri that are not holidays (weekday() 0=Mon ... 4=Fri)."""
    return d.weekday() < 5 and d not in HOLIDAYS_2026


def _next_business_day(d: date) -> date:
    """The first business day strictly after d."""
    d += timedelta(days=1)
    while not is_business_day(d):
        d += timedelta(days=1)
    return d


def _open_dt(d: date) -> datetime:
    return datetime.combine(d, OPEN_TIME)


def _close_dt(d: date) -> datetime:
    return datetime.combine(d, CLOSE_TIME)


def roll_forward(dt: datetime) -> datetime:
    """Move dt to the nearest moment inside business hours (never backwards).

    - inside business hours -> unchanged
    - before opening on a business day -> same day 09:30
    - after closing, weekend or holiday -> next business day 09:30
    """
    if is_business_day(dt.date()):
        if dt < _open_dt(dt.date()):
            return _open_dt(dt.date())
        if dt < _close_dt(dt.date()):
            return dt
    return _open_dt(_next_business_day(dt.date()))


def add_business_minutes(start: datetime, minutes: int) -> datetime:
    """Return the time reached after `minutes` of business time from start."""
    if minutes < 0:
        raise ValueError("minutes must be >= 0")
    current = roll_forward(start)
    remaining = minutes
    while True:
        # Minutes left in the current business day.
        available = int((_close_dt(current.date()) - current).total_seconds() // 60)
        if remaining <= available:
            return current + timedelta(minutes=remaining)
        # Use up today, continue at the next business day's opening.
        remaining -= available
        current = _open_dt(_next_business_day(current.date()))


def business_minutes_between(a: datetime, b: datetime) -> int:
    """Whole business minutes between a and b (0 if b <= a)."""
    if b <= a:
        return 0
    total_seconds = 0.0
    day = a.date()
    while day <= b.date():
        if is_business_day(day):
            # Overlap of [a, b] with this day's [09:30, 18:00].
            window_start = max(a, _open_dt(day))
            window_end = min(b, _close_dt(day))
            if window_end > window_start:
                total_seconds += (window_end - window_start).total_seconds()
        day += timedelta(days=1)
    return int(total_seconds // 60)