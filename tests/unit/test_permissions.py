import psycopg
import pytest
from fastapi import Depends, Request

from app.core.db import connection
from app.core.outcomes import Outcome, Refusal
from app.core.permissions import Actor, authorize, permission
from tests.support import recorder

WEN = Actor(account_id=7, name="Wen", role="USER")
ADMIN = Actor(account_id=2, name="Admin1", role="ADMIN")


@permission("tests.admins_only")
def _admins_only(actor: Actor, resource: object | None) -> bool:
    return actor.role == "ADMIN"


@permission("tests.owner_of_resource")
def _owner_of_resource(actor: Actor, resource: object | None) -> bool:
    return resource == actor.account_id


@permission("tests.rule_that_answers_nothing")
def _answers_nothing(actor: Actor, resource: object | None):
    return None


@permission("tests.rule_that_answers_truthy_but_not_true")
def _answers_truthy(actor: Actor, resource: object | None):
    return "yes"


def refused(actor: Actor, action: str, resource: object | None = None) -> Refusal:
    with pytest.raises(Refusal) as caught:
        authorize(actor, action, resource)
    return caught.value


def test_an_action_whose_rule_allows_is_authorized():
    authorize(ADMIN, "tests.admins_only")
    authorize(WEN, "tests.owner_of_resource", 7)


@pytest.mark.parametrize(
    ("actor", "action", "resource"),
    [
        (ADMIN, "tests.never_registered", None),
        (WEN, "tests.admins_only", None),
        (WEN, "tests.owner_of_resource", 8),
        (ADMIN, "tests.rule_that_answers_nothing", None),
        (ADMIN, "tests.rule_that_answers_truthy_but_not_true", None),
    ],
)
def test_anything_not_explicitly_allowed_is_forbidden(actor, action, resource):
    refusal = refused(actor, action, resource)

    assert refusal.outcome is Outcome.FORBIDDEN
    assert refusal.message == "禁止存取"
    assert refusal.attempted == action


def test_an_action_cannot_be_registered_twice():
    with pytest.raises(ValueError):
        permission("tests.admins_only")(lambda actor, resource: True)


@pytest.fixture
def routes(app, database_url):
    with psycopg.connect(database_url) as conn:
        conn.execute("create table note (body text)")

    @app.post("/_test/signed-in/forbidden")
    def signed_in(request: Request, conn=Depends(connection)):
        request.state.actor = WEN
        conn.execute("insert into note values ('must not survive')")
        authorize(WEN, "tests.never_registered")

    @app.post("/_test/anonymous/forbidden")
    def anonymous(conn=Depends(connection)):
        conn.execute("insert into note values ('must not survive')")
        raise Refusal(Outcome.FORBIDDEN, "禁止存取", attempted="tests.never_registered")

    @app.post("/_test/signed-in/conflict")
    def conflict(request: Request, conn=Depends(connection)):
        request.state.actor = WEN
        raise Refusal(Outcome.CONFLICT, "不行")


def test_forbidden_for_a_signed_in_actor_leaves_exactly_one_access_denied_row(client, clock, database_url, routes):
    before = recorder.snapshot(database_url)

    response = client.post("/_test/signed-in/forbidden", headers={"Accept": "application/json"})

    assert response.status_code == 403
    assert response.json() == {"outcome": "FORBIDDEN", "message": "禁止存取"}
    changes = recorder.diff(before, recorder.snapshot(database_url))
    assert [(change.table, change.kind) for change in changes] == [("audit_log", "added")]
    row = changes[0].after
    assert (row["actor_account_id"], row["actor_name"], row["type"]) == (7, "Wen", "ACCESS_DENIED")
    assert "tests.never_registered" in row["description"]
    with psycopg.connect(database_url) as conn:
        assert conn.execute("select at from audit_log").fetchall() == [(clock.now(),)]


def test_forbidden_without_an_actor_writes_nothing(client, database_url, routes):
    before = recorder.snapshot(database_url)

    response = client.post("/_test/anonymous/forbidden")

    assert response.status_code == 403
    assert recorder.diff(before, recorder.snapshot(database_url)) == []


def test_other_refusals_of_a_signed_in_actor_write_no_audit_row(client, database_url, routes):
    before = recorder.snapshot(database_url)

    response = client.post("/_test/signed-in/conflict")

    assert response.status_code == 409
    assert recorder.diff(before, recorder.snapshot(database_url)) == []
