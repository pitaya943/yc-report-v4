"""The PostgreSQL server the tests run against, and the databases they create on it."""

import glob
import os
import shutil
import socket
import subprocess
import tempfile
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

# PostgreSQL refuses to run as root; the cluster then runs as this system user.
UNPRIVILEGED_USER = "postgres"


def _bin_dir() -> Path:
    candidates = [os.environ.get("PG_BIN", "")]
    pg_config = shutil.which("pg_config")
    if pg_config:
        candidates.append(subprocess.run([pg_config, "--bindir"], capture_output=True, text=True).stdout.strip())
    candidates += sorted(glob.glob("/usr/lib/postgresql/*/bin"), reverse=True)
    for candidate in candidates:
        if candidate and (Path(candidate) / "initdb").exists():
            return Path(candidate)
    raise RuntimeError(
        "No PostgreSQL binaries found (initdb, pg_ctl). Install PostgreSQL, set PG_BIN to its "
        "bin directory, or set TEST_DATABASE_URL to a server where databases can be created."
    )


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def throwaway_cluster() -> Iterator[str]:
    """Start a cluster in a temporary directory, yield its URL, remove it afterwards."""
    bin_dir = _bin_dir()
    as_user = {"user": UNPRIVILEGED_USER} if os.geteuid() == 0 else {}
    root = Path(tempfile.mkdtemp(prefix="yc-test-pg-"))
    data = root / "data"
    port = _free_port()

    def run(*command: str) -> None:
        done = subprocess.run(command, capture_output=True, text=True, cwd=root, **as_user)
        if done.returncode != 0:
            raise RuntimeError(f"{command[0]} failed:\n{done.stdout}\n{done.stderr}")

    started = False
    try:
        if as_user:
            shutil.chown(root, user=UNPRIVILEGED_USER)
        run(str(bin_dir / "initdb"), "-D", str(data), "-U", "postgres", "-A", "trust", "-E", "UTF8", "--locale=C")
        options = f"-p {port} -c listen_addresses=127.0.0.1 -c unix_socket_directories='' -c fsync=off"
        run(str(bin_dir / "pg_ctl"), "-D", str(data), "-l", str(root / "log"), "-o", options, "-w", "start")
        started = True
        yield f"postgresql://postgres@127.0.0.1:{port}/postgres"
    finally:
        if started:
            run(str(bin_dir / "pg_ctl"), "-D", str(data), "-m", "immediate", "-w", "stop")
        shutil.rmtree(root)


@contextmanager
def test_server(environ: Mapping[str, str]) -> Iterator[str]:
    """The URL of a server where databases can be created.

    TEST_DATABASE_URL if set; otherwise a throwaway cluster of our own.
    """
    url = environ.get("TEST_DATABASE_URL", "").strip()
    if url:
        yield url
    else:
        with throwaway_cluster() as own:
            yield own


test_server.__test__ = False  # not a test, despite the name


def url_for(server_url: str, database: str) -> str:
    return make_conninfo(**{**conninfo_to_dict(server_url), "dbname": database})


def create_database(server_url: str, *, template: str | None = None) -> str:
    """Create a database with a fresh name, optionally as a copy of ``template``."""
    name = f"yc_test_{uuid.uuid4().hex}"
    statement = sql.SQL("create database {}").format(sql.Identifier(name))
    if template is not None:
        statement += sql.SQL(" template {}").format(sql.Identifier(template))
    with psycopg.connect(server_url, autocommit=True) as conn:
        conn.execute(statement)
    return name


@contextmanager
def databases(server_url: str, template: str | None) -> Iterator[Callable[[], str]]:
    """Yields a function that creates a database and returns its URL; drops them all on exit."""
    created: list[str] = []

    def make() -> str:
        created.append(create_database(server_url, template=template))
        return url_for(server_url, created[-1])

    try:
        yield make
    finally:
        for name in created:
            drop_database(server_url, name)


def drop_database(server_url: str, name: str) -> None:
    with psycopg.connect(server_url, autocommit=True) as conn:
        conn.execute(sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(name)))
