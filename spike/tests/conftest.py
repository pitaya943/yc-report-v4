"""A throwaway PostgreSQL cluster for the test session, and a clean schema per test.

Set SPIKE_DATABASE_URL to use an existing empty database instead.
PostgreSQL refuses to run as root, so when the tests run as root the server
is started as the OS user named by SPIKE_PG_OS_USER (default: postgres).
"""
import glob
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import psycopg
import pytest

SCHEMA = Path(__file__).parent.parent / "spike_jobs" / "schema.sql"


def _pg_bin() -> str:
    if os.environ.get("PG_BIN"):
        return os.environ["PG_BIN"]
    if shutil.which("pg_config"):
        return subprocess.check_output(["pg_config", "--bindir"], text=True).strip()
    found = sorted(glob.glob("/usr/lib/postgresql/*/bin"))
    if not found:
        raise RuntimeError("PostgreSQL binaries not found; set PG_BIN")
    return found[-1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def database_url():
    if os.environ.get("SPIKE_DATABASE_URL"):
        yield os.environ["SPIKE_DATABASE_URL"]
        return

    bin_dir = _pg_bin()
    data = tempfile.mkdtemp(prefix="spike-pg-")
    as_user = []
    if os.geteuid() == 0:
        user = os.environ.get("SPIKE_PG_OS_USER", "postgres")
        shutil.chown(data, user)
        as_user = ["runuser", "-u", user, "--"]
    port = _free_port()

    def run(*args):
        subprocess.run([*as_user, *args], check=True, capture_output=True, cwd=data)

    run(f"{bin_dir}/initdb", "-D", data, "-U", "spike", "-A", "trust", "-E", "UTF8")
    run(
        f"{bin_dir}/pg_ctl", "-D", data, "-w", "start", "-l", f"{data}/log",
        "-o", f"-p {port} -c listen_addresses=127.0.0.1 -c unix_socket_directories={data}",
    )
    try:
        yield f"postgresql://spike@127.0.0.1:{port}/postgres"
    finally:
        run(f"{bin_dir}/pg_ctl", "-D", data, "-m", "immediate", "stop")
        shutil.rmtree(data, ignore_errors=True)


@pytest.fixture
def db(database_url):
    """The URL of a database holding the empty schema."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS archive, session")
        conn.execute(SCHEMA.read_text())
    return database_url


@pytest.fixture
def connect(db):
    """Open autocommit connections; each one stands for a separate worker process."""
    opened = []

    def _connect(**kwargs):
        conn = psycopg.connect(db, **{"autocommit": True, **kwargs})
        opened.append(conn)
        return conn

    yield _connect
    for conn in opened:
        conn.close()


def archives(conn) -> list[tuple[str, str]]:
    """Automatic archives as (kind, ISO date), oldest first."""
    return [
        (kind, d.isoformat())
        for kind, d in conn.execute(
            "SELECT kind, period_date FROM archive WHERE automatic ORDER BY period_date, kind"
        )
    ]
