"""The only place that reads the system time."""

from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")


class Clock(Protocol):
    def now(self) -> datetime:
        """The current moment, always timezone-aware in Asia/Taipei."""
        ...


class SystemClock:
    def __init__(self, offset_minutes: int = 0):
        self._offset = timedelta(minutes=offset_minutes)

    def now(self) -> datetime:
        return datetime.now(TAIPEI) + self._offset
