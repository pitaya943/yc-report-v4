"""Requests that are in flight at the same moment, for the tests of what must not race."""

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import psycopg
from psycopg import sql

TIMEOUT_SECONDS = 30


def run_together[T](database_url: str, table: str, calls: list[Callable[[], T]]) -> list[T]:
    """Run the calls so that all of them are inside their transactions at once; return their results in order.

    Writes to ``table`` are held back while the calls start, each on a thread
    of its own. Only when every one of them is waiting on a lock (the table's,
    or one that another call holds) are they let go. Each call must write to
    ``table``, or wait for a call that does.
    """
    with psycopg.connect(database_url) as holder, ThreadPoolExecutor(len(calls)) as pool:
        holder.execute(sql.SQL("lock table {} in share mode").format(sql.Identifier(table)))
        futures = [pool.submit(call) for call in calls]
        try:
            with psycopg.connect(database_url, autocommit=True) as watcher:
                deadline = time.monotonic() + TIMEOUT_SECONDS
                while _waiting(watcher) < len(calls):
                    if time.monotonic() > deadline:
                        raise AssertionError(f"only {_waiting(watcher)} of {len(calls)} calls came to wait on a lock")
                    time.sleep(0.01)
        finally:
            holder.rollback()
        return [future.result() for future in futures]


def _waiting(conn: psycopg.Connection) -> int:
    (count,) = conn.execute(
        "select count(*) from pg_stat_activity"
        " where datname = current_database() and wait_event_type = 'Lock'"
    ).fetchone()
    return count
