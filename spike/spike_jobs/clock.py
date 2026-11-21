"""The one source of time. Nothing else in the spike reads the system clock."""
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(TAIPEI)


class FixedClock:
    """A clock a test sets by hand. Accepts any timezone-aware instant."""

    def __init__(self, at: datetime | str):
        self.set(at)

    def set(self, at: datetime | str) -> None:
        if isinstance(at, str):
            at = datetime.fromisoformat(at)
        if at.tzinfo is None:
            at = at.replace(tzinfo=TAIPEI)
        self._at = at

    def now(self) -> datetime:
        return self._at
