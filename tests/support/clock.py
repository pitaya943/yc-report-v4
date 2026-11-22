from datetime import datetime, timedelta

from app.core.clock import TAIPEI


class TestClock:
    """A clock the test sets and moves."""

    __test__ = False

    def __init__(self, start: datetime | None = None):
        self._now = start or datetime(2026, 1, 5, 9, 0, tzinfo=TAIPEI)

    def now(self) -> datetime:
        return self._now

    def set(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            raise ValueError("the test clock needs a timezone-aware moment")
        self._now = moment.astimezone(TAIPEI)

    def advance(self, **delta: float) -> None:
        self._now += timedelta(**delta)
