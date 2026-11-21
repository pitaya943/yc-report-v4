"""The jobs against a real PostgreSQL, driven by the injected clock."""
import threading
import time
from datetime import date, datetime

import pytest

from conftest import archives
from spike_jobs.clock import TAIPEI, FixedClock
from spike_jobs.jobs import (
    build_placeholder,
    claim_automatic_archive,
    delete_expired_sessions,
    run_due_archives,
    tick,
)


def test_archive_is_created_when_the_clock_reaches_2359(connect):
    conn = connect()
    clock = FixedClock("2026-11-15T23:58:59")
    run_due_archives(conn, clock)  # fresh install: archives 2026-11-14, the latest due date
    assert archives(conn) == [("daily", "2026-11-14")]

    clock.set("2026-11-15T23:59:00")
    assert run_due_archives(conn, clock) == [("daily", date(2026, 11, 15))]

    assert archives(conn) == [("daily", "2026-11-14"), ("daily", "2026-11-15")]
    created_at, content = conn.execute(
        "SELECT created_at, content FROM archive WHERE period_date = '2026-11-15'"
    ).fetchone()
    assert created_at == datetime(2026, 11, 15, 23, 59, tzinfo=TAIPEI)
    assert content == "placeholder daily 2026-11-15"


def test_running_again_after_a_restart_does_not_duplicate(connect):
    clock = FixedClock("2026-11-30T23:59:00")
    before_restart = connect()
    run_due_archives(before_restart, clock)
    before_restart.close()

    after_restart = connect()
    clock.set("2026-11-30T23:59:40")
    assert run_due_archives(after_restart, clock) == []
    assert archives(after_restart) == [("daily", "2026-11-30"), ("monthly", "2026-11-30")]


def test_app_down_at_2359_for_several_days_catches_up_every_missed_date(connect):
    conn = connect()
    run_due_archives(conn, FixedClock("2026-11-27T23:59:00"))

    # down from the 28th; back on 2 December at 08:00
    run_due_archives(conn, FixedClock("2026-12-02T08:00:00"))

    assert archives(conn) == [
        ("daily", "2026-11-27"),
        ("daily", "2026-11-28"),
        ("daily", "2026-11-29"),
        ("daily", "2026-11-30"),
        ("monthly", "2026-11-30"),
        ("daily", "2026-12-01"),
    ]


def test_leap_year_month_end_is_archived_on_29_february(connect):
    conn = connect()
    run_due_archives(conn, FixedClock("2028-02-27T23:59:00"))
    run_due_archives(conn, FixedClock("2028-02-28T23:59:00"))
    assert ("monthly", "2028-02-28") not in archives(conn)
    run_due_archives(conn, FixedClock("2028-02-29T23:59:00"))
    assert [a for a in archives(conn) if a[0] == "monthly"] == [("monthly", "2028-02-29")]


def test_a_crash_while_building_leaves_nothing_and_the_next_run_completes_it(connect):
    conn = connect()
    clock = FixedClock("2026-11-15T23:59:00")

    def crash(conn, kind, period_date):
        raise RuntimeError("process killed while collecting reports")

    with pytest.raises(RuntimeError):
        run_due_archives(conn, clock, build=crash)
    assert archives(conn) == []

    run_due_archives(conn, clock)
    assert archives(conn) == [("daily", "2026-11-15")]


def test_a_manual_archive_for_the_same_date_does_not_replace_the_automatic_one(connect):
    conn = connect()
    conn.execute(
        "INSERT INTO archive (kind, period_date, automatic, created_at)"
        " VALUES ('daily', '2026-11-15', false, '2026-11-15T10:00+08')"
    )
    conn.execute(
        "INSERT INTO archive (kind, period_date, automatic, created_at)"
        " VALUES ('daily', '2026-11-15', false, '2026-11-15T11:00+08')"
    )
    run_due_archives(conn, FixedClock("2026-11-15T23:59:00"))
    assert archives(conn) == [("daily", "2026-11-15")]
    assert conn.execute("SELECT count(*) FROM archive").fetchone()[0] == 3


def _wait_until_finished_or_blocked(observer, thread, backend_pid):
    """Return once the worker thread has ended or its backend waits on a lock."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not thread.is_alive():
            return
        waiting = observer.execute(
            "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = %s",
            (backend_pid,),
        ).fetchone()
        if waiting and waiting[0]:
            return
        time.sleep(0.01)
    raise AssertionError("second worker neither finished nor blocked within 10 s")


def test_two_workers_in_overlapping_transactions_produce_exactly_one_archive(connect):
    """Worker A has inserted but not committed when worker B runs the same job.

    The overlap is forced, not hoped for: A's transaction stays open until B
    has either finished or is blocked on A's row. With the unique index, B
    blocks, then sees the conflict and creates nothing. Without it, B cannot
    see A's uncommitted row and inserts a second one, every time.
    """
    clock = FixedClock("2026-11-15T23:59:00")
    day = date(2026, 11, 15)

    worker_a = connect(autocommit=False)
    assert claim_automatic_archive(worker_a, "daily", day, clock.now()) is True
    build_placeholder(worker_a, "daily", day)
    # A has not committed.

    worker_b = connect()
    b_pid = worker_b.info.backend_pid
    b_created = []
    thread = threading.Thread(target=lambda: b_created.extend(run_due_archives(worker_b, clock)))
    thread.start()
    _wait_until_finished_or_blocked(connect(), thread, b_pid)

    worker_a.commit()
    thread.join(timeout=10)
    assert not thread.is_alive()

    count = connect().execute(
        "SELECT count(*) FROM archive WHERE automatic AND kind = 'daily' AND period_date = %s",
        (day,),
    ).fetchone()[0]
    assert count == 1, f"{count} automatic daily archives for {day}"
    assert b_created == []


def test_eight_workers_released_at_the_same_instant_produce_one_archive_each_round(connect):
    rounds, workers = 25, 8
    conns = [connect() for _ in range(workers)]
    observer = connect()
    # History up to 30 November, so each round has exactly one due archive.
    run_due_archives(observer, FixedClock("2026-11-30T23:59:00"))

    for n in range(rounds):
        clock = FixedClock(datetime(2026, 12, 1 + n, 23, 59, tzinfo=TAIPEI))
        barrier = threading.Barrier(workers)
        created = []

        def work(conn):
            barrier.wait()
            created.extend(run_due_archives(conn, clock))

        threads = [threading.Thread(target=work, args=(c,)) for c in conns]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        expected_day = date(2026, 12, 1 + n)
        assert created == [("daily", expected_day)], f"round {n}"
        count = observer.execute(
            "SELECT count(*) FROM archive WHERE automatic AND kind = 'daily' AND period_date = %s",
            (expected_day,),
        ).fetchone()[0]
        assert count == 1, f"round {n}: {count} automatic daily archives for {expected_day}"


def test_expired_sessions_are_deleted_and_live_ones_kept(connect):
    conn = connect()
    for expires_at in ("2026-11-15T09:00+08", "2026-11-15T12:00:00+08", "2026-11-15T12:00:01+08"):
        conn.execute("INSERT INTO session (expires_at) VALUES (%s)", (expires_at,))

    deleted = delete_expired_sessions(conn, FixedClock("2026-11-15T12:00:00"))

    assert deleted == 2
    remaining = [r[0] for r in conn.execute("SELECT expires_at FROM session")]
    assert remaining == [datetime(2026, 11, 15, 12, 0, 1, tzinfo=TAIPEI)]


def test_one_tick_runs_both_the_archives_and_the_session_cleanup(db, connect):
    conn = connect()
    conn.execute("INSERT INTO session (expires_at) VALUES ('2026-11-15T09:00+08')")

    tick(db, FixedClock("2026-11-15T23:59:00"))

    assert archives(conn) == [("daily", "2026-11-15")]
    assert conn.execute("SELECT count(*) FROM session").fetchone()[0] == 0
