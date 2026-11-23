"""The constraints of design section 8 hold in the database itself."""

import psycopg
import pytest

INSERT = "insert into accounts (display_name, role, zone, big_meter, password_hash) values "


@pytest.fixture
def conn(database_url):
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(INSERT + "('Kuei', 'OWNER', 'WEST', false, 'h'), ('Wen', 'USER', 'WEST', false, 'h')")
        yield connection


def test_accounts_that_keep_the_rules_are_accepted(conn):
    conn.execute(INSERT + "('Big', 'USER', 'SOUTH', true, 'h'), ('Admin1', 'ADMIN', 'WEST', false, 'h')")
    conn.execute("update accounts set archived_at = '2026-11-15T10:00:00+08:00' where display_name = 'Wen'")
    conn.execute("update accounts set failed_count = 4 where display_name = 'Wen'")


@pytest.mark.parametrize(
    "statement",
    [
        INSERT + "('Wen', 'USER', 'SOUTH', false, 'h')",  # the name is taken
        INSERT + "('New', 'GUEST', 'WEST', false, 'h')",
        INSERT + "('New', 'USER', 'NORTH', false, 'h')",
        INSERT + "('New', 'ADMIN', 'WEST', true, 'h')",  # the big-meter flag is for users only
        INSERT + "('New', 'OWNER', 'WEST', false, 'h')",  # there is one owner
        "update accounts set role = 'OWNER' where display_name = 'Wen'",
        "update accounts set archived_at = '2026-11-15T10:00:00+08:00' where display_name = 'Kuei'",
        "update accounts set failed_count = -1 where display_name = 'Wen'",
        "insert into sessions (account_id, token_hash, csrf_token, created_at, last_used_at)"
        " values (999, 't', 'c', '2026-11-15T10:00:00+08:00', '2026-11-15T10:00:00+08:00')",
    ],
)
def test_the_database_refuses_what_breaks_them(conn, statement):
    with pytest.raises(psycopg.IntegrityError):
        conn.execute(statement)


def test_two_sessions_cannot_share_a_token_hash(conn):
    session = (
        "insert into sessions (account_id, token_hash, csrf_token, created_at, last_used_at)"
        " select id, 'same', 'c', '2026-11-15T10:00:00+08:00', '2026-11-15T10:00:00+08:00' from accounts"
        " where display_name = 'Wen'"
    )
    conn.execute(session)
    with pytest.raises(psycopg.IntegrityError):
        conn.execute(session)
