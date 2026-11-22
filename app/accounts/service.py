"""Sign-in and sessions: the rules of design section 9."""

import hashlib
import secrets
from datetime import timedelta

from psycopg import Connection

from app.accounts import store
from app.accounts.passwords import Passwords
from app.core.clock import Clock
from app.core.outcomes import Outcome, Refusal
from app.core.permissions import Actor

GROUP_LABELS = {"admin": "管理員", "west": "西區", "south": "南區"}
LANDING_PAGES = {"USER": "/reports", "ADMIN": "/review", "OWNER": "/review"}
# A session not used for this long has timed out; exactly this long counts.
IDLE_LIMIT = timedelta(minutes=30)


def names_for_group(conn: Connection, group: str | None) -> list[str]:
    if group not in store.GROUPS:
        raise Refusal(Outcome.INVALID, "請選擇類型")
    return store.names_in_group(conn, group)


def sign_in(
    conn: Connection,
    clock: Clock,
    passwords: Passwords,
    *,
    group: str | None,
    name: str | None,
    password: str,
) -> tuple[Actor, str]:
    """Check the fields, the account and the password; return who signed in and their session token.

    The group may be left out (None); the interface always sends it.
    """
    listed = names_for_group(conn, group) if group is not None else None
    if not name or (listed is not None and name not in listed):
        raise Refusal(Outcome.INVALID, "請選擇帳戶")

    credentials = store.credentials_of(conn, name)
    if credentials is None:
        # Unknown and archived accounts cost a verification too, so the time
        # taken says nothing about whether the account exists.
        passwords.verify_for_nobody(password)
        raise Refusal(Outcome.UNAUTHENTICATED, "密碼錯誤，請重試")
    if not passwords.verify(credentials.password_hash, password):
        raise Refusal(Outcome.UNAUTHENTICATED, "密碼錯誤，請重試")

    token = secrets.token_urlsafe(32)
    store.insert_session(
        conn,
        account_id=credentials.actor.account_id,
        token_hash=_token_hash(token),
        csrf_token=secrets.token_urlsafe(32),
        at=clock.now(),
    )
    return credentials.actor, token


def use_session(conn: Connection, clock: Clock, token: str) -> store.Session | None:
    """The session a token belongs to, or None when it is no longer good.

    Using a session restarts its idle window, and nothing else does. One found
    idle for too long is ended for good.
    """
    session = store.lock_open_session(conn, _token_hash(token))
    if session is None:
        return None
    now = clock.now()
    if session.last_used_at + IDLE_LIMIT <= now:
        store.end_session(conn, session.id, now)
        return None
    store.touch_session(conn, session.id, now)
    return session


def sign_out(conn: Connection, clock: Clock, session: store.Session) -> None:
    store.end_session(conn, session.id, clock.now())


def create_account(
    conn: Connection,
    passwords: Passwords,
    *,
    name: str,
    role: str,
    zone: str,
    big_meter: bool,
    password: str,
) -> int:
    return store.insert_account(
        conn, name=name, role=role, zone=zone, big_meter=big_meter, password_hash=passwords.hash(password)
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
