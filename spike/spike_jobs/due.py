"""Which automatic archives are due now. Pure: no database, no system time.

An archive for date D is due once the clock reaches D 23:59 Asia/Taipei.
The answer depends only on the instant and on what has already been archived,
so a late, repeated or missed trigger gives the same result as a punctual one.
"""
from calendar import monthrange
from datetime import date, datetime, time, timedelta

from .clock import TAIPEI

DAILY = "daily"
MONTHLY = "monthly"
CUTOFF = time(23, 59)


def latest_due_date(now: datetime) -> date:
    """The most recent date whose 23:59 Asia/Taipei has been reached."""
    local = now.astimezone(TAIPEI)
    if local.time() >= CUTOFF:
        return local.date()
    return local.date() - timedelta(days=1)


def is_month_end(d: date) -> bool:
    return d.day == monthrange(d.year, d.month)[1]


def due_archives(
    now: datetime,
    first_archived: date | None,
    last_archived: dict[str, date],
) -> list[tuple[str, date]]:
    """Archives to create now, oldest first.

    first_archived: the earliest date that has any automatic archive, or None
        on a fresh install. Nothing before it is ever created, so a new
        installation starts with the latest due date instead of back-filling.
    last_archived: per kind, the latest date that has an automatic archive.
    """
    latest = latest_due_date(now)
    start = first_archived or latest
    due = []
    d = start
    while d <= latest:
        if d > last_archived.get(DAILY, date.min):
            due.append((DAILY, d))
        if is_month_end(d) and d > last_archived.get(MONTHLY, date.min):
            due.append((MONTHLY, d))
        d += timedelta(days=1)
    return due
