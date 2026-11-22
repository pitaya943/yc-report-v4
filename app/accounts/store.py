"""SQL for accounts, sessions and sign-in attempts."""

from dataclasses import dataclass
from datetime import datetime

from psycopg import Connection

from app.core.permissions import Actor

# First key of the advisory locks taken per client address; the second key is
# a hash of the address. The migration lock uses the one-key form, which
# PostgreSQL keeps apart from this one.
_ADDRESS_LOCK_SPACE = 9402


@dataclass(frozen=True)
class Credentials:
    actor: Actor
    password_hash: str
    failed_count: int
    last_failed_at: datetime | None
    locked_until: datetime | None


@dataclass(frozen=True)
class Session:
    id: int
    actor: Actor
    csrf_token: str
    last_used_at: datetime


def names_in_group(conn: Connection, *, roles: tuple[str, ...], zone: str | None) -> list[str]:
    """The display names of the accounts with these roles (and zone, if given) that are not archived, in name order."""
    rows = conn.execute(
        "select display_name from accounts"
        " where role = any(%s) and (%s::text is null or zone = %s) and archived_at is null"
        " order by display_name",
        (list(roles), zone, zone),
    )
    return [name for (name,) in rows]


def count_attempts_since(conn: Connection, address: str, since: datetime) -> int:
    """How many attempts this address made after ``since``.

    Takes the address's lock first and holds it until the transaction ends, so
    attempts from one address are counted one at a time, whichever process
    serves them.
    """
    conn.execute("select pg_advisory_xact_lock(%s, hashtext(%s))", (_ADDRESS_LOCK_SPACE, address))
    (count,) = conn.execute(
        "select count(*) from sign_in_attempts where client_address = %s and attempted_at > %s",
        (address, since),
    ).fetchone()
    return count


def insert_attempt(conn: Connection, address: str, at: datetime) -> None:
    conn.execute("insert into sign_in_attempts (client_address, attempted_at) values (%s, %s)", (address, at))


def credentials_for_sign_in(conn: Connection, name: str) -> Credentials | None:
    """The account of that name with its password hash and failure state, unless it is archived.

    Locks the account's row until the transaction ends: two sign-ins for one
    account are decided one after the other.
    """
    row = conn.execute(
        "select id, display_name, role, password_hash, failed_count, last_failed_at, locked_until"
        " from accounts where display_name = %s and archived_at is null for update",
        (name,),
    ).fetchone()
    if row is None:
        return None
    account_id, display_name, role, password_hash, failed_count, last_failed_at, locked_until = row
    return Credentials(Actor(account_id, display_name, role), password_hash, failed_count, last_failed_at, locked_until)


def set_failure_state(
    conn: Connection,
    account_id: int,
    *,
    failed_count: int,
    last_failed_at: datetime | None,
    locked_until: datetime | None,
) -> None:
    conn.execute(
        "update accounts set failed_count = %s, last_failed_at = %s, locked_until = %s where id = %s",
        (failed_count, last_failed_at, locked_until, account_id),
    )


def insert_account(
    conn: Connection, *, name: str, role: str, zone: str, big_meter: bool, password_hash: str
) -> int:
    (account_id,) = conn.execute(
        "insert into accounts (display_name, role, zone, big_meter, password_hash)"
        " values (%s, %s, %s, %s, %s) returning id",
        (name, role, zone, big_meter, password_hash),
    ).fetchone()
    return account_id


def insert_session(
    conn: Connection, *, account_id: int, token_hash: str, csrf_token: str, at: datetime
) -> None:
    conn.execute(
        "insert into sessions (account_id, token_hash, csrf_token, created_at, last_used_at)"
        " values (%s, %s, %s, %s, %s)",
        (account_id, token_hash, csrf_token, at, at),
    )


def lock_open_session(conn: Connection, token_hash: str) -> Session | None:
    """The session with this token, if it has not ended and the account is not archived.

    The row stays locked until the transaction ends, so two requests of one
    session read and move ``last_used_at`` one after the other.
    """
    row = conn.execute(
        "select s.id, s.csrf_token, s.last_used_at, a.id, a.display_name, a.role"
        " from sessions s join accounts a on a.id = s.account_id"
        " where s.token_hash = %s and s.ended_at is null and a.archived_at is null"
        " for update of s",
        (token_hash,),
    ).fetchone()
    if row is None:
        return None
    session_id, csrf_token, last_used_at, *account = row
    return Session(session_id, Actor(*account), csrf_token, last_used_at)


def touch_session(conn: Connection, session_id: int, at: datetime) -> None:
    conn.execute("update sessions set last_used_at = %s where id = %s", (at, session_id))


def end_session(conn: Connection, session_id: int, at: datetime) -> None:
    conn.execute("update sessions set ended_at = %s where id = %s", (at, session_id))
