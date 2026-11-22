import socket
import subprocess
import sys
import time

import httpx2
import psycopg
import uvicorn

from app.__main__ import main

from tests.support.cli import REPO, app_environ


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_serve(database_url: str, port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "app", "serve", "--port", str(port)],
        cwd=REPO,
        env=app_environ(DATABASE_URL=database_url),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def accepts_connections(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def test_serve_has_migrated_by_the_time_it_answers(empty_database):
    port = free_port()
    server = start_serve(empty_database, port)
    try:
        deadline = time.monotonic() + 30
        status = None
        while status is None and time.monotonic() < deadline and server.poll() is None:
            try:
                status = httpx2.get(f"http://127.0.0.1:{port}/health", timeout=5).status_code
            except httpx2.TransportError:
                time.sleep(0.1)

        assert status == 200, server.poll()
        with psycopg.connect(empty_database) as conn:
            assert conn.execute("select to_regclass('audit_log') is not null").fetchone() == (True,)
            assert conn.execute("select count(*) > 0 from schema_migrations").fetchone() == (True,)
    finally:
        server.terminate()
        server.communicate(timeout=30)


def test_serve_does_not_start_when_the_migration_fails(empty_database):
    # An applied migration whose recorded content differs from the file on disk.
    with psycopg.connect(empty_database) as conn:
        conn.execute(
            "create table schema_migrations (version integer primary key, filename text not null,"
            " sha256 text not null, applied_at timestamptz not null)"
        )
        conn.execute(
            "insert into schema_migrations values (1, '0001_audit_log.sql', 'not-the-hash', '2026-01-01T00:00:00+08:00')"
        )
    port = free_port()
    server = start_serve(empty_database, port)
    try:
        _, stderr = server.communicate(timeout=30)
    finally:
        server.kill()

    assert server.returncode not in (0, None)
    assert "0001_audit_log.sql" in stderr
    assert "migration 失敗" in stderr
    assert not accepts_connections(port)


def test_serve_reports_a_database_error_after_migrating_under_its_own_wording(
    empty_database, monkeypatch, capsys
):
    def fail_to_start(*args, **kwargs):
        raise psycopg.OperationalError("the pool could not be opened")

    monkeypatch.setattr(uvicorn, "run", fail_to_start)
    monkeypatch.setenv("DATABASE_URL", empty_database)

    status = main(["serve"])

    stderr = capsys.readouterr().err
    assert status != 0
    assert "資料庫錯誤：the pool could not be opened" in stderr
    assert "migration" not in stderr


def test_serve_reports_an_unreachable_database_as_a_migration_failure(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"postgresql://nobody@127.0.0.1:{free_port()}/nothing?connect_timeout=3")

    status = main(["serve"])

    stderr = capsys.readouterr().err
    assert status != 0
    assert stderr.startswith("migration 失敗：")
