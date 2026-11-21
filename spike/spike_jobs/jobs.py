"""The scheduled jobs. Every function takes the clock; none knows what triggers it."""
from datetime import date, datetime
from typing import Callable

import psycopg

from .clock import Clock
from .due import due_archives

Build = Callable[[psycopg.Connection, str, date], None]


def claim_automatic_archive(
    conn: psycopg.Connection, kind: str, period_date: date, now: datetime
) -> bool:
    """Insert the archive row inside the caller's transaction.

    True if this caller owns the archive. If another transaction is inserting
    the same kind and date, this waits for it to end, then returns False when
    it committed (or True when it rolled back).
    """
    row = conn.execute(
        "INSERT INTO archive (kind, period_date, automatic, created_at)"
        " VALUES (%s, %s, true, %s)"
        " ON CONFLICT (kind, period_date) WHERE automatic DO NOTHING"
        " RETURNING id",
        (kind, period_date, now),
    ).fetchone()
    return row is not None


def build_placeholder(conn: psycopg.Connection, kind: str, period_date: date) -> None:
    """Stands in for collecting the day's confirmed reports."""
    conn.execute(
        "UPDATE archive SET content = %s WHERE kind = %s AND period_date = %s AND automatic",
        (f"placeholder {kind} {period_date}", kind, period_date),
    )


def run_due_archives(
    conn: psycopg.Connection, clock: Clock, build: Build = build_placeholder
) -> list[tuple[str, date]]:
    """Create every automatic archive that is due and missing; return those created.

    conn must be in autocommit mode: each archive is one transaction holding
    both the row and its content, so a crash leaves either all of it or none.
    """
    now = clock.now()
    rows = conn.execute(
        "SELECT kind, min(period_date), max(period_date) FROM archive"
        " WHERE automatic GROUP BY kind"
    ).fetchall()
    first = min((r[1] for r in rows), default=None)
    last = {r[0]: r[2] for r in rows}

    created = []
    for kind, period_date in due_archives(now, first, last):
        with conn.transaction():
            if claim_automatic_archive(conn, kind, period_date, now):
                build(conn, kind, period_date)
                created.append((kind, period_date))
    return created


def delete_expired_sessions(conn: psycopg.Connection, clock: Clock) -> int:
    """Delete sessions whose expiry time has been reached; return how many."""
    return conn.execute(
        "DELETE FROM session WHERE expires_at <= %s", (clock.now(),)
    ).rowcount


def tick(database_url: str, clock: Clock) -> None:
    """Everything a trigger has to do. Safe to call at any time, any number of times."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        run_due_archives(conn, clock)
        delete_expired_sessions(conn, clock)
