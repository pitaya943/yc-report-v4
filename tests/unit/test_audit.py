import re

import psycopg
import pytest

from app.core import audit
from app.core.permissions import Actor
from tests.support.cli import REPO

WEN = Actor(account_id=7, name="Wen", role="USER")


def rows(database_url: str) -> list[tuple]:
    with psycopg.connect(database_url) as conn:
        return conn.execute(
            "select at, actor_account_id, actor_name, type, description from audit_log order by id"
        ).fetchall()


def test_a_row_commits_with_the_callers_transaction(database_url, clock):
    with psycopg.connect(database_url) as conn:
        audit.write(conn, clock, WEN, audit.AuditType.REPORT_CREATE, "建立回報，共 2 人作業")
        assert rows(database_url) == []
        conn.commit()

    assert rows(database_url) == [(clock.now(), 7, "Wen", "REPORT_CREATE", "建立回報，共 2 人作業")]


def test_a_row_rolls_back_with_the_callers_transaction(database_url, clock):
    with psycopg.connect(database_url) as conn:
        audit.write(conn, clock, WEN, audit.AuditType.REPORT_CREATE, "建立回報")
        conn.rollback()

    assert rows(database_url) == []


def test_the_system_actor_is_recorded_without_an_account(database_url, clock):
    with psycopg.connect(database_url) as conn:
        audit.write(conn, clock, audit.SYSTEM, audit.AuditType.ACCOUNT_LOCKOUT, "鎖定")

    assert rows(database_url) == [(clock.now(), None, "SYSTEM", "ACCOUNT_LOCKOUT", "鎖定")]


@pytest.mark.parametrize("type", ["ACCOUNT_DELETE", "SOMETHING_ELSE", "access_denied", ""])
def test_a_type_outside_appendix_c_is_refused(database_url, clock, type):
    with psycopg.connect(database_url) as conn:
        with pytest.raises(ValueError):
            audit.write(conn, clock, WEN, type, "x")

    assert rows(database_url) == []


def test_the_constants_are_exactly_the_types_of_appendix_c():
    appendix = (REPO / "docs/spec/reference/appendix-c-audit-types.md").read_text(encoding="utf-8")
    table = [line for line in appendix.splitlines() if line.startswith("|")]
    documented = set(re.findall(r"`([A-Z_]+)`", "\n".join(table)))

    assert len(documented) == 37
    assert {member.value for member in audit.AuditType} == documented
    assert {member.name for member in audit.AuditType} == documented


@pytest.mark.parametrize(
    "statement",
    [
        "update audit_log set description = 'changed'",
        "update audit_log set description = 'changed' where false",
        "delete from audit_log",
        "delete from audit_log where false",
        "truncate audit_log",
        "truncate audit_log restart identity cascade",
    ],
)
def test_the_database_refuses_to_change_or_remove_audit_rows(database_url, clock, statement):
    with psycopg.connect(database_url) as conn:
        audit.write(conn, clock, WEN, audit.AuditType.EXPORT, "匯出")
    before = rows(database_url)

    with psycopg.connect(database_url) as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute(statement)

    assert rows(database_url) == before and len(before) == 1
