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


def actor_of_session(conn: Connection, token_hash: str) -> Actor | None:
    """Whose session this is, if it has not ended and the account is not archived."""
    row = conn.execute(
        "select a.id, a.display_name, a.role from sessions s join accounts a on a.id = s.account_id"
        " where s.token_hash = %s and s.ended_at is null and a.archived_at is null",
        (token_hash,),
    ).fetchone()
    return Actor(*row) if row else None
