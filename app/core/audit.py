"""The audit trail: rows are written in the caller's transaction and never changed."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from psycopg import Connection

from app.core.clock import Clock

if TYPE_CHECKING:
    from app.core.permissions import Actor


class AuditType(StrEnum):
    """The types of docs/spec/reference/appendix-c-audit-types.md, and no others."""

    REPORT_CREATE = "REPORT_CREATE"
    REPORT_UPDATE = "REPORT_UPDATE"
    REPORT_DELETE = "REPORT_DELETE"
    REPORT_CONFIRM = "REPORT_CONFIRM"
    REPORT_REJECT = "REPORT_REJECT"
    REPORT_UNCONFIRM = "REPORT_UNCONFIRM"
    ACCOUNT_CREATE = "ACCOUNT_CREATE"
    ACCOUNT_UPDATE = "ACCOUNT_UPDATE"
    ACCOUNT_ARCHIVE = "ACCOUNT_ARCHIVE"
    ACCOUNT_RESTORE = "ACCOUNT_RESTORE"
    ACCOUNT_ROLE_CHANGE = "ACCOUNT_ROLE_CHANGE"
    ACCOUNT_LOCKOUT = "ACCOUNT_LOCKOUT"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    BANK_REVEAL = "BANK_REVEAL"
    MATERIAL_REQUEST = "MATERIAL_REQUEST"
    MATERIAL_CANCEL = "MATERIAL_CANCEL"
    MATERIAL_ADD = "MATERIAL_ADD"
    MATERIAL_UPDATE = "MATERIAL_UPDATE"
    MATERIAL_DELETE = "MATERIAL_DELETE"
    MATERIAL_APPROVE = "MATERIAL_APPROVE"
    MATERIAL_REJECT = "MATERIAL_REJECT"
    MATERIAL_IMPORT = "MATERIAL_IMPORT"
    MATERIAL_RESET = "MATERIAL_RESET"
    MATERIAL_KEEP_A = "MATERIAL_KEEP_A"
    MATERIAL_SYNC_B = "MATERIAL_SYNC_B"
    SYSTEM_CONFIG = "SYSTEM_CONFIG"
    RETENTION_SET = "RETENTION_SET"
    RETENTION_RESET = "RETENTION_RESET"
    RETENTION_YEAR_END = "RETENTION_YEAR_END"
    LEDGER_CREATE = "LEDGER_CREATE"
    LEDGER_UPDATE = "LEDGER_UPDATE"
    LEDGER_DELETE = "LEDGER_DELETE"
    LEDGER_SETTLE = "LEDGER_SETTLE"
    LEDGER_VOID = "LEDGER_VOID"
    EXPORT = "EXPORT"
    FILE_DOWNLOAD = "FILE_DOWNLOAD"
    ACCESS_DENIED = "ACCESS_DENIED"


class SystemActor:
    """The actor of automatic actions. Recorded with no account id."""

    name = "SYSTEM"


SYSTEM: Final = SystemActor()


def write(
    conn: Connection,
    clock: Clock,
    actor: Actor | SystemActor,
    type: str,
    description: str,
) -> None:
    """Add one audit row on ``conn``; it commits or rolls back with the caller's work."""
    if type not in AuditType:
        raise ValueError(f"not an audit type of appendix C: {type}")
    account_id = None if actor is SYSTEM else actor.account_id
    conn.execute(
        "insert into audit_log (at, actor_account_id, actor_name, type, description)"
        " values (%s, %s, %s, %s, %s)",
        (clock.now(), account_id, actor.name, str(type), description),
    )
