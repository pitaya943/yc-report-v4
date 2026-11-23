"""The contract of tests/steps/common: each assertion holds when it should and fails when it should."""

from datetime import datetime

import psycopg
import pytest
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from pytest_bdd.steps import step_function_context_registry

from app.core import audit
from app.core.clock import TAIPEI
from app.core.db import connection
from app.core.outcomes import Outcome, Refusal
from app.core.permissions import Actor
from app.core.web import current_actor
from tests.steps.common import steps
from tests.support.spec import SpecStep
from tests.support.world import SYSTEM, World, parse_moment


@pytest.fixture(autouse=True)
def routes(app, database_url):
    with psycopg.connect(database_url) as conn:
        conn.execute("create table note (id integer primary key, body text)")

    @app.post("/_test/nothing")
    def nothing():
        return {"ok": True}

    @app.post("/_test/refuse/{name}")
    def refuse(name: str):
        raise Refusal(Outcome[name], "此顯示名稱已被使用")

    @app.post("/_test/note")
    def note(conn=Depends(connection)):
        conn.execute("insert into note values (1, 'written')")
        return {"ok": True}

    @app.post("/_test/audit/{type}/{count}")
    def write_audit(request: Request, type: str, count: int, by: str = SYSTEM, conn=Depends(connection)):
        actor = audit.SYSTEM
        if by != SYSTEM:
            account_id = conn.execute("select id from accounts where display_name = %s", (by,)).fetchone()[0]
            actor = Actor(account_id, by, "USER")
        for _ in range(count):
            audit.write(conn, request.app.state.clock, actor, type, "測試")
        return {"ok": True}

    @app.post("/_test/audit-under-a-borrowed-name")
    def borrowed_name(request: Request, conn=Depends(connection)):
        (wei,) = conn.execute("select id from accounts where display_name = 'Wei'").fetchone()
        audit.write(conn, request.app.state.clock, Actor(wei, "Wen", "USER"), "EXPORT", "測試")
        return {"ok": True}

    @app.post("/_test/disagreeing/{what}")
    def disagreeing(what: str):
        body = {"outcome": "INVALID" if what == "body" else "CONFLICT", "message": "此顯示名稱已被使用"}
        headers = {} if what == "header" else {"X-Outcome": "CONFLICT"}
        return JSONResponse(body, status_code=400 if what == "status" else 409, headers=headers)

    @app.post("/_test/crash")
    def crash():
        raise RuntimeError("boom")

    @app.post("/_test/labelled-success")
    def labelled_success():
        return JSONResponse({"ok": True}, headers={"X-Outcome": "CONFLICT"})

    @app.get("/_test/who")
    def who(actor: Actor = Depends(current_actor)):
        return {"name": actor.name}


def fails(assertion, *args, **kwargs) -> None:
    with pytest.raises(AssertionError):
        assertion(*args, **kwargs)


# The background


def test_a_scenario_starts_from_the_shared_background_of_the_spec(world: World, database_url):
    # The values of docs/spec/background.md.
    assert world.clock.now() == datetime(2026, 11, 15, 10, 0, tzinfo=TAIPEI)
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(
            "select display_name, role, zone, big_meter, archived_at is not null from accounts order by id"
        ).fetchall()
    assert rows == [
        ("Kuei", "OWNER", "WEST", False, False),
        ("Admin1", "ADMIN", "WEST", False, False),
        ("Admin2", "ADMIN", "WEST", False, False),
        ("Wen", "USER", "WEST", False, False),
        ("Wei", "USER", "WEST", False, False),
        ("Wan", "USER", "WEST", False, False),
        ("Nan", "USER", "SOUTH", False, False),
        ("Big", "USER", "WEST", True, False),
        ("Old", "USER", "WEST", False, True),
    ]
    assert world.accounts["Nan"]["zone"] == "SOUTH"


def test_a_background_step_that_nothing_loads_fails_the_scenario(world: World):
    fails(world.load_background, [SpecStep("", "Given", "the moon is full")])


def test_moments_are_read_as_taipei_time_with_or_without_seconds():
    assert parse_moment("2026-11-15 23:59") == datetime(2026, 11, 15, 23, 59, tzinfo=TAIPEI)
    assert parse_moment("2026-11-15 10:29:59") == datetime(2026, 11, 15, 10, 29, 59, tzinfo=TAIPEI)


def test_the_clock_step_sets_the_test_clock(world: World):
    steps.the_clock_is(world, "2027-01-05 10:00")

    assert world.clock.now() == datetime(2027, 1, 5, 10, 0, tzinfo=TAIPEI)


# Sessions


def test_a_signed_in_person_sends_requests_as_themselves_and_a_visitor_as_nobody(world: World):
    steps.is_signed_in(world, "Wen")
    steps.is_signed_in(world, "Admin1")

    assert world.send("GET", "/_test/who", actor="Wen").json() == {"name": "Wen"}
    assert world.send("GET", "/_test/who", actor="Admin1").json() == {"name": "Admin1"}
    # The sessions used before do not travel with a visitor's request.
    assert world.send("GET", "/_test/who").status_code == 401


def test_signing_in_is_not_part_of_what_the_request_wrote(world: World):
    world.sign_in("Wen")
    world.send("POST", "/_test/nothing", actor="Wen")

    world.assert_nothing_written()


# Outcomes


def test_rejected_checks_the_class_on_every_response(world: World):
    world.send("POST", "/_test/refuse/CONFLICT")

    world.assert_rejected("CONFLICT")
    world.assert_rejected("CONFLICT", "此顯示名稱已被使用")
    fails(world.assert_rejected, "BLOCKED")  # the same status, another class
    fails(world.assert_rejected, "INVALID")
    fails(world.assert_rejected, "CONFLICT", "此顯示名稱已被使用。")

    world.send("POST", "/_test/nothing")
    fails(world.assert_rejected, "CONFLICT")  # one of the two was not refused


@pytest.mark.parametrize("what", ["status", "header", "body"])
def test_rejected_needs_the_status_the_header_and_the_body_to_agree(world: World, what):
    world.send("POST", f"/_test/disagreeing/{what}")

    fails(world.assert_rejected, "CONFLICT")


@pytest.mark.parametrize("path", ["/_test/crash", "/_test/labelled-success"])
def test_accepted_fails_on_an_error_and_on_a_response_labelled_as_a_refusal(world: World, path):
    world.send("POST", path)

    fails(world.assert_accepted)


def test_rejected_and_accepted_fail_when_no_request_was_sent(world: World):
    fails(world.assert_rejected, "CONFLICT")
    fails(world.assert_accepted)


def test_accepted_means_no_response_was_a_refusal_or_an_error(world: World):
    world.send("POST", "/_test/nothing")
    world.assert_accepted()

    world.send("POST", "/_test/refuse/INVALID")
    fails(world.assert_accepted)


def test_the_outcome_step_takes_a_class_accepted_or_a_registered_success(world: World, monkeypatch):
    world.send("POST", "/_test/refuse/INVALID")
    steps.the_outcome_is(world, "INVALID", None)
    steps.the_outcome_is(world, "INVALID", "此顯示名稱已被使用")
    fails(steps.the_outcome_is, world, "INVALID", "別的訊息")
    fails(steps.the_outcome_is, world, "accepted", None)
    fails(steps.the_outcome_is, world, "FORBIDDEN", None)
    fails(steps.the_outcome_is, world, "signed in", None)  # nobody has said what it means

    seen = []
    monkeypatch.setitem(steps.SUCCESS_OUTCOMES, "signed in", seen.append)
    steps.the_outcome_is(world, "signed in", "")
    assert seen == [world]


def test_accepted_in_the_outcome_step(world: World):
    world.send("POST", "/_test/nothing")

    steps.the_outcome_is(world, "accepted", "")
    fails(steps.the_outcome_is, world, "INVALID", None)


# What was written


def test_nothing_is_written_fails_on_any_change(world: World):
    world.send("POST", "/_test/nothing")
    world.assert_nothing_written()
    world.assert_no_audit_row_written()
    world.assert_nothing_else_written()

    world.send("POST", "/_test/note")
    fails(world.assert_nothing_written)
    fails(world.assert_nothing_else_written)
    world.assert_no_audit_row_written()  # only the audit table is looked at


def test_an_audit_row_is_exactly_one_row_of_that_type(world: World):
    world.send("POST", "/_test/audit/EXPORT/1")

    fails(world.assert_nothing_written)
    fails(world.assert_no_audit_row_written)
    fails(world.assert_audit_rows_written, "FILE_DOWNLOAD")
    fails(world.assert_audit_rows_written, "EXPORT", count=2)
    world.assert_audit_rows_written("EXPORT")

    world.send("POST", "/_test/audit/EXPORT/1")
    fails(world.assert_audit_rows_written, "EXPORT")
    world.assert_audit_rows_written("EXPORT", count=2)


def test_the_actor_of_an_audit_row_is_a_person_or_the_system(world: World):
    world.send("POST", "/_test/audit/REPORT_CREATE/1", params={"by": "Wen"})
    world.send("POST", "/_test/audit/ACCOUNT_LOCKOUT/1")

    world.assert_audit_rows_written("REPORT_CREATE", actor="Wen")
    fails(world.assert_audit_rows_written, "REPORT_CREATE", actor="Wei")
    fails(world.assert_audit_rows_written, "REPORT_CREATE", actor=SYSTEM)
    world.assert_audit_rows_written("ACCOUNT_LOCKOUT", actor=SYSTEM)
    fails(world.assert_audit_rows_written, "ACCOUNT_LOCKOUT", actor="Wen")


def test_the_actor_of_an_audit_row_is_matched_by_account_and_not_by_name_alone(world: World):
    world.send("POST", "/_test/audit-under-a-borrowed-name")

    fails(world.assert_audit_rows_written, "EXPORT", actor="Wen")
    fails(world.assert_audit_rows_written, "EXPORT", actor="Wei")
    world.assert_audit_rows_written("EXPORT")


def test_nothing_else_is_written_leaves_out_only_the_audit_rows_already_asserted(world: World):
    world.send("POST", "/_test/audit/EXPORT/1")
    world.send("POST", "/_test/audit/FILE_DOWNLOAD/1")

    fails(world.assert_nothing_else_written)
    world.assert_audit_rows_written("EXPORT")
    fails(world.assert_nothing_else_written)  # FILE_DOWNLOAD has not been asserted
    world.assert_audit_rows_written("FILE_DOWNLOAD")
    world.assert_nothing_else_written()

    world.send("POST", "/_test/note")
    fails(world.assert_nothing_else_written)


def test_the_two_rows_step_and_the_except_step(world: World):
    world.send("POST", "/_test/audit/REPORT_CONFIRM/1", params={"by": "Wen"})
    fails(steps.two_audit_rows_are_written, world, "REPORT_CONFIRM", "REPORT_UPDATE")
    steps.nothing_is_written_except_an_audit_row(world, "REPORT_CONFIRM", '"Wen"')

    world.send("POST", "/_test/audit/REPORT_UPDATE/1")
    steps.two_audit_rows_are_written(world, "REPORT_CONFIRM", "REPORT_UPDATE")
    fails(steps.nothing_is_written_except_an_audit_row, world, "REPORT_CONFIRM", '"Wei"')

    world.send("POST", "/_test/note")
    fails(steps.nothing_is_written_except_an_audit_row, world, "REPORT_CONFIRM", None)


# The wording of the steps


@pytest.mark.parametrize(
    ("keyword", "text", "definition", "arguments"),
    [
        ("given", 'the clock is "2026-11-15 10:00" in Asia/Taipei', "the_clock_is", {"moment": "2026-11-15 10:00"}),
        ("given", 'the clock is "2027-01-05 10:00"', "the_clock_is", {"moment": "2027-01-05 10:00"}),
        ("given", '"Wen" is signed in', "is_signed_in", {"name": "Wen"}),
        (
            "then",
            "the request is rejected as UNAUTHENTICATED",
            "the_request_is_rejected",
            {"outcome": "UNAUTHENTICATED", "message": None},
        ),
        (
            "then",
            'the request is rejected as RATE_LIMITED with message "登入嘗試過於頻繁，請稍後再試"',
            "the_request_is_rejected",
            {"outcome": "RATE_LIMITED", "message": "登入嘗試過於頻繁，請稍後再試"},
        ),
        ("then", "the outcome is accepted", "the_outcome_is", {"outcome": "accepted", "message": None}),
        ("then", "the outcome is signed in", "the_outcome_is", {"outcome": "signed in", "message": None}),
        (
            "then",
            'the outcome is INVALID with message "請選擇角色"',
            "the_outcome_is",
            {"outcome": "INVALID", "message": "請選擇角色"},
        ),
        ("then", 'the outcome is accepted with message ""', "the_outcome_is", {"outcome": "accepted", "message": ""}),
        ("then", "nothing is written", "nothing_is_written", {}),
        ("then", "no audit row is written", "no_audit_row_is_written", {}),
        (
            "then",
            'an audit row "MATERIAL_ADD" is written',
            "an_audit_row_is_written",
            {"type": "MATERIAL_ADD", "actor": None},
        ),
        (
            "then",
            'an audit row "ACCESS_DENIED" is written with actor "Wen"',
            "an_audit_row_is_written",
            {"type": "ACCESS_DENIED", "actor": '"Wen"'},
        ),
        (
            "then",
            'an audit row "ACCOUNT_LOCKOUT" is written with actor SYSTEM',
            "an_audit_row_is_written",
            {"type": "ACCOUNT_LOCKOUT", "actor": "SYSTEM"},
        ),
        (
            "then",
            'exactly 1 audit row "REPORT_CONFIRM" is written',
            "exactly_n_audit_rows_are_written",
            {"count": "1", "type": "REPORT_CONFIRM", "actor": None},
        ),
        (
            "then",
            'exactly 1 audit row "ACCESS_DENIED" is written with actor "Wen"',
            "exactly_n_audit_rows_are_written",
            {"count": "1", "type": "ACCESS_DENIED", "actor": '"Wen"'},
        ),
        (
            "then",
            'audit rows "REPORT_UPDATE" and "REPORT_CONFIRM" are written',
            "two_audit_rows_are_written",
            {"first": "REPORT_UPDATE", "second": "REPORT_CONFIRM"},
        ),
        ("then", "nothing else is written", "nothing_else_is_written", {}),
        (
            "then",
            'nothing is written except an audit row "RETENTION_SET"',
            "nothing_is_written_except_an_audit_row",
            {"type": "RETENTION_SET", "actor": None},
        ),
        (
            "then",
            'nothing is written except an audit row "ACCESS_DENIED" with actor "Wen"',
            "nothing_is_written_except_an_audit_row",
            {"type": "ACCESS_DENIED", "actor": '"Wen"'},
        ),
    ],
)
def test_each_phrasing_of_the_spec_reaches_its_common_step(keyword, text, definition, arguments):
    common = [
        context
        for context in step_function_context_registry.values()
        if context.step_func.__module__ == steps.__name__
    ]
    matching = [c for c in common if c.type == keyword and c.parser.is_matching(text)]

    assert [c.step_func.__name__ for c in matching] == [definition]
    assert matching[0].parser.parse_arguments(text) == arguments


@pytest.mark.parametrize(
    "text",
    [
        'an audit row "PASSWORD_CHANGE" is written with actor "Wen" naming "Wei"',
        'an audit row "SYSTEM_CONFIG" is written with the old and new value',
        'the other is rejected as CONFLICT with message "此回報已被處理"',
        "a later protected request from that session is rejected as UNAUTHENTICATED",
    ],
)
def test_phrasings_that_belong_to_one_area_are_left_to_it(text):
    common = [c for c in step_function_context_registry.values() if c.step_func.__module__ == steps.__name__]

    assert [c.step_func.__name__ for c in common if c.parser.is_matching(text)] == []
