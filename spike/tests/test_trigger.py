"""The trigger on its own, and the trigger inside real server processes."""
import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from spike_jobs.clock import TAIPEI
from spike_jobs.trigger import run_forever

SPIKE_DIR = Path(__file__).parent.parent


def test_the_loop_keeps_ticking_after_a_tick_fails():
    calls = []

    def tick():
        calls.append(len(calls))
        if len(calls) == 1:
            raise ConnectionError("database unreachable")

    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_forever(tick, 30, sleep=sleep))

    assert calls == [0, 1, 2]
    assert sleeps == [30, 30, 30]


def test_the_one_shot_command_runs_a_tick_on_the_system_clock(db, connect):
    """`python -m spike_jobs`: what a platform cron or a person would run."""
    env = {**os.environ, "DATABASE_URL": db, "PYTHONPATH": str(SPIKE_DIR)}
    started = datetime.now(TAIPEI).date()
    for _ in range(2):
        subprocess.run([sys.executable, "-m", "spike_jobs"], env=env, cwd=SPIKE_DIR, check=True)
    rows = connect().execute("SELECT kind, period_date, automatic FROM archive").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "daily" and rows[0][2] is True
    assert rows[0][1] in (started, started - timedelta(days=1))


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(db, port):
    env = {**os.environ, "DATABASE_URL": db, "TICK_SECONDS": "0.2", "PYTHONPATH": str(SPIKE_DIR)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "spike_jobs.app:app", "--port", str(port), "--workers", "2"],
        env=env, cwd=SPIKE_DIR, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            return proc
        except OSError:
            time.sleep(0.1)
    _stop_server(proc)
    raise AssertionError("server did not start")


def _stop_server(proc):
    os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()


def test_two_real_server_processes_and_a_restart_make_one_archive(db, connect):
    """uvicorn with two worker processes, each running the loop on the system clock.

    Shows that the loop really runs inside server processes and that killing
    and restarting them leaves one archive. It does not prove the guard: the
    two processes rarely start within the same millisecond. That proof is
    test_two_workers_in_overlapping_transactions_produce_exactly_one_archive.

    On a fresh database the only due archive is the latest due date, which by
    the system clock is today (after 23:59 Taipei) or yesterday.
    """
    conn = connect()
    count = "SELECT count(*) FROM archive"
    started = datetime.now(TAIPEI).date()

    server = _start_server(db, _free_port())
    try:
        deadline = time.monotonic() + 20
        while conn.execute(count).fetchone()[0] == 0 and time.monotonic() < deadline:
            time.sleep(0.1)
        time.sleep(1.5)  # several more ticks from both processes
    finally:
        _stop_server(server)  # SIGKILL: an abrupt stop, as in a crash or redeploy

    rows = conn.execute("SELECT kind, period_date, automatic FROM archive").fetchall()
    assert len(rows) == 1
    kind, period_date, automatic = rows[0]
    assert (kind, automatic) == ("daily", True)
    assert period_date in (started, started - timedelta(days=1))

    server = _start_server(db, _free_port())
    try:
        time.sleep(1.5)
    finally:
        _stop_server(server)
    if datetime.now(TAIPEI).date() == started:  # no new date became due meanwhile
        assert conn.execute(count).fetchone()[0] == 1
