"""The trigger: calls a tick again and again. It decides nothing about what is due."""
import asyncio
import logging
from typing import Awaitable, Callable

log = logging.getLogger(__name__)


async def run_forever(
    tick: Callable[[], None],
    interval_seconds: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            # The database may be briefly unreachable; the next tick catches up.
            log.exception("scheduled tick failed")
        await sleep(interval_seconds)
