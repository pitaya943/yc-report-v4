"""Sign-in and sessions: the rules of design section 9."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from psycopg import Connection

from app.accounts import store
from app.accounts.passwords import Passwords
from app.core import audit
from app.core.clock import Clock
from app.core.outcomes import Outcome, Refusal
from app.core.permissions import Actor


@dataclass(frozen=True)
class Group:
    """One choice of the sign-in page's group picker and the accounts it lists."""

    label: str
    roles: tuple[str, ...]
    zone: str | None = None


# The only list of sign-in groups: the picker and the checks both read it.
# The owner signs in under "admin".
GROUPS = {
    "admin": Group("管理員", roles=("OWNER", "ADMIN")),
    "west": Group("西區", roles=("USER",), zone="WEST"),
    "south": Group("南區", roles=("USER",), zone="SOUTH"),
}
LANDING_PAGES = {"USER": "/reports", "ADMIN": "/review", "OWNER": "/review"}

ATTEMPTS_PER_WINDOW = 10
ATTEMPT_WINDOW = timedelta(seconds=60)
FAILURES_BEFORE_LOCK = 5
LOCK_DURATION = timedelta(minutes=15)
QUIET_PERIOD = timedelta(minutes=15)


def names_for_group(conn: Connection, group: str | None) -> list[str]:
    chosen = GROUPS.get(group) if group is not None else None
    if chosen is None:
        raise Refusal(Outcome.INVALID, "請選擇類型")
    return store.names_in_group(conn, roles=chosen.roles, zone=chosen.zone)


def sign_in(
    conn: Connection,
    clock: Clock,
    passwords: Passwords,
    *,
    address: str,
    group: str | None,
    name: str | None,
    password: str,
) -> tuple[Actor, str]:
    """Decide one sign-in attempt from ``address``, in the order of design section 9.2.

    Returns who signed in and their session token. The group may be left out
    (None); the interface always sends it.

    Once the attempt reaches an account or a password, a refusal is preceded
    by ``conn.commit()``, which keeps what was counted (the attempt, the
    failure, the lock): the one place where a refused request leaves
    something behind.
    """
    now = clock.now()

    if store.count_attempts_since(conn, address, now - ATTEMPT_WINDOW) >= ATTEMPTS_PER_WINDOW:
        raise Refusal(Outcome.RATE_LIMITED, "登入嘗試過於頻繁，請稍後再試")
    store.insert_attempt(conn, address, now)

    listed = names_for_group(conn, group) if group is not None else None
    # PostgreSQL text cannot hold a NUL, so such a name is nobody's.
    if not name or "\x00" in name or (listed is not None and name not in listed):
        raise Refusal(Outcome.INVALID, "請選擇帳戶")

    credentials = store.credentials_for_sign_in(conn, name)
    if credentials is None:
        # Unknown and archived accounts cost a verification too, so the time
        # taken says nothing about whether the account exists.
        passwords.verify_for_nobody(password)
        conn.commit()
        raise Refusal(Outcome.UNAUTHENTICATED, "密碼錯誤，請重試")

    account_id = credentials.actor.account_id
    failed_count = credentials.failed_count
    if credentials.locked_until is not None:
        if now < credentials.locked_until:
            conn.commit()
            raise Refusal(Outcome.LOCKED, "密碼錯誤次數過多，請在 15 分鐘後再試")
        failed_count = 0
    elif failed_count and now - credentials.last_failed_at >= QUIET_PERIOD:
        failed_count = 0

    if not passwords.verify(credentials.password_hash, password):
        failed_count += 1
        locking = failed_count >= FAILURES_BEFORE_LOCK
        store.set_failure_state(
            conn,
            account_id,
            failed_count=failed_count,
            last_failed_at=now,
            locked_until=now + LOCK_DURATION if locking else None,
        )
        if locking:
            audit.write(
                conn,
                clock,
                audit.SYSTEM,
                audit.AuditType.ACCOUNT_LOCKOUT,
                f"{credentials.actor.name}：連續 {FAILURES_BEFORE_LOCK} 次密碼錯誤，鎖定 15 分鐘",
            )
        conn.commit()
        if locking:
            raise Refusal(Outcome.LOCKED, "密碼錯誤次數過多，請在 15 分鐘後再試")
        raise Refusal(Outcome.UNAUTHENTICATED, "密碼錯誤，請重試")

    store.set_failure_state(conn, account_id, failed_count=0, last_failed_at=None, locked_until=None)
    token = secrets.token_urlsafe(32)
    store.insert_session(
        conn,
        account_id=credentials.actor.account_id,
        token_hash=_token_hash(token),
        csrf_token=secrets.token_urlsafe(32),
        at=now,
    )
    return credentials.actor, token


def actor_of_token(conn: Connection, token: str) -> Actor | None:
    """The person a session token belongs to, or None when it is no longer good."""
    return store.actor_of_session(conn, _token_hash(token))


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
