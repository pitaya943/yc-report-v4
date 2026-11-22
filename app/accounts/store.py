"""SQL for accounts and sessions."""

from dataclasses import dataclass
from datetime import datetime

from psycopg import Connection

from app.core.permissions import Actor

# Which accounts each sign-in group lists. The owner signs in under "admin".
_GROUP_FILTER = {
    "admin": "role in ('OWNER', 'ADMIN')",
    "west": "role = 'USER' and zone = 'WEST'",
    "south": "role = 'USER' and zone = 'SOUTH'",
}
GROUPS = tuple(_GROUP_FILTER)


@dataclass(frozen=True)
class Credentials:
    actor: Actor
    password_hash: str


@dataclass(frozen=True)
class Session:
    id: int
    actor: Actor
    csrf_token: str
    last_used_at: datetime


def names_in_group(conn: Connection, group: str) -> list[str]:
    """The display names of the group's accounts that are not archived, in name order."""
    rows = conn.execute(
        "select display_name from accounts"
        f" where {_GROUP_FILTER[group]} and archived_at is null order by display_name"
    )
    return [name for (name,) in rows]


def credentials_of(conn: Connection, name: str) -> Credentials | None:
    """The account of that name and its password hash, unless it is archived."""
    row = conn.execute(
        "select id, display_name, role, password_hash from accounts"
        " where display_name = %s and archived_at is null",
        (name,),
    ).fetchone()
    if row is None:
        return None
    account_id, display_name, role, password_hash = row
    return Credentials(Actor(account_id, display_name, role), password_hash)


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
