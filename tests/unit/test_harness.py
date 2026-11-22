import socket
from pathlib import Path

import psycopg
import pytest

from app.core import audit
from tests.support import pg, recorder
from tests.support.recorder import Change


def listening(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def test_without_a_url_the_harness_runs_its_own_cluster_and_removes_it():
    with pg.test_server({}) as url:
        with psycopg.connect(url) as conn:
            data_directory = Path(conn.execute("show data_directory").fetchone()[0])
            name = pg.create_database(url)
            pg.drop_database(url, name)
            port = int(conn.execute("show port").fetchone()[0])
        assert data_directory.exists()
        assert listening(port)

    assert not data_directory.exists()
    assert not data_directory.parent.exists()
    assert not listening(port)
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(url, connect_timeout=3)


def test_with_a_url_the_harness_uses_that_server(pg_server):
    with psycopg.connect(pg_server) as conn:
        data_directory = conn.execute("show data_directory").fetchone()[0]

    with pg.test_server({"TEST_DATABASE_URL": pg_server}) as url:
        assert url == pg_server
        with psycopg.connect(url) as conn:
            assert conn.execute("show data_directory").fetchone()[0] == data_directory

    # Still running: it was not ours to stop.
    with psycopg.connect(pg_server) as conn:
        conn.execute("select 1")


def test_each_database_is_a_migrated_copy_that_shares_no_data(make_database, clock):
    first, second = make_database(), make_database()

    with psycopg.connect(first) as conn:
        audit.write(conn, clock, audit.SYSTEM, audit.AuditType.EXPORT, "只在第一個資料庫")

    with psycopg.connect(first) as conn:
        assert conn.execute("select count(*) from audit_log").fetchone() == (1,)
    with psycopg.connect(second) as conn:
        assert conn.execute("select count(*) from audit_log").fetchone() == (0,)
        assert conn.execute("select count(*) > 0 from schema_migrations").fetchone() == (True,)


def test_databases_are_dropped_afterwards(pg_server, template_database):
    with pg.databases(pg_server, template_database) as make:
        with psycopg.connect(make()) as conn:
            name = conn.execute("select current_database()").fetchone()[0]
        with psycopg.connect(pg_server) as conn:
            assert conn.execute("select count(*) from pg_database where datname = %s", (name,)).fetchone() == (1,)

    with psycopg.connect(pg_server) as conn:
        assert conn.execute("select count(*) from pg_database where datname = %s", (name,)).fetchone() == (0,)


@pytest.fixture
def tables(database_url):
    with psycopg.connect(database_url) as conn:
        conn.execute("create table keyed (id integer primary key, body text)")
        conn.execute("create table unkeyed (body text)")
        conn.execute("create table sessions (id integer primary key, last_used_at timestamptz, ended_at timestamptz)")
        conn.execute("insert into keyed values (1, 'one'), (2, 'two')")
        conn.execute("insert into unkeyed values ('same'), ('same')")
        conn.execute("insert into sessions values (1, '2026-01-05T09:00:00+08:00', null)")
    return database_url


def changes_after(database_url: str, *statements: str) -> list[Change]:
    before = recorder.snapshot(database_url)
    with psycopg.connect(database_url) as conn:
        for statement in statements:
            conn.execute(statement)
    return recorder.diff(before, recorder.snapshot(database_url))


def test_the_recorder_reports_nothing_when_nothing_changed(tables):
    assert changes_after(tables) == []
    assert changes_after(tables, "update keyed set body = body") == []


def test_the_recorder_reports_an_added_row(tables):
    assert changes_after(tables, "insert into keyed values (3, 'three')") == [
        Change("keyed", "added", None, {"id": 3, "body": "three"})
    ]


def test_the_recorder_reports_a_changed_row(tables):
    assert changes_after(tables, "update keyed set body = 'TWO' where id = 2") == [
        Change("keyed", "changed", {"id": 2, "body": "two"}, {"id": 2, "body": "TWO"})
    ]


def test_the_recorder_reports_a_deleted_row(tables):
    assert changes_after(tables, "delete from keyed where id = 1") == [
        Change("keyed", "deleted", {"id": 1, "body": "one"}, None)
    ]


def test_the_recorder_sees_rows_of_tables_without_a_key_even_identical_ones(tables):
    assert changes_after(tables, "insert into unkeyed values ('same')") == [
        Change("unkeyed", "added", None, {"body": "same"})
    ]
    assert [c.kind for c in changes_after(tables, "delete from unkeyed")] == ["deleted"] * 3


def test_the_recorder_sees_every_table_including_new_ones_and_the_audit_log(tables, clock):
    before = recorder.snapshot(tables)
    with psycopg.connect(tables) as conn:
        conn.execute("create table later (n integer)")
        conn.execute("insert into later values (1)")
        audit.write(conn, clock, audit.SYSTEM, audit.AuditType.EXPORT, "匯出")

    changes = recorder.diff(before, recorder.snapshot(tables))

    assert [(c.table, c.kind) for c in changes] == [("audit_log", "added"), ("later", "added")]


def test_the_recorder_ignores_only_the_listed_columns(tables):
    assert recorder.IGNORED_COLUMNS == {("sessions", "last_used_at")}

    assert changes_after(tables, "update sessions set last_used_at = '2026-01-05T09:10:00+08:00'") == []

    ended = changes_after(tables, "update sessions set ended_at = '2026-01-05T09:10:00+08:00'")
    assert [(c.table, c.kind) for c in ended] == [("sessions", "changed")]

    # The same column name in another table is not ignored.
    with psycopg.connect(tables) as conn:
        conn.execute("create table visits (id integer primary key, last_used_at timestamptz)")
        conn.execute("insert into visits values (1, '2026-01-05T09:00:00+08:00')")
    moved = changes_after(tables, "update visits set last_used_at = '2026-01-05T09:10:00+08:00'")
    assert [(c.table, c.kind) for c in moved] == [("visits", "changed")]
