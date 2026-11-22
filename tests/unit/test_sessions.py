"""Session lifetime, sign-out and the anti-forgery check: what the spec's scenarios do not pin down."""

import dataclasses
import json
from datetime import datetime
from importlib.metadata import version

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.support.cli import REPO
from tests.support.html import alert_texts, elements
from tests.support.world import CSRF_FIELD, CSRF_HEADER, PASSWORD, SESSION_COOKIE, World

BROWSER = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
WEN = {"group": "west", "name": "Wen", "password": PASSWORD}


@pytest.fixture(autouse=True)
def routes(app):
    @app.api_route("/_test/change", methods=["POST", "PUT", "PATCH", "DELETE"])
    def change():
        return {"ok": True}


def cookie_attributes(response) -> set[str]:
    [cookie] = response.headers.get_list("set-cookie")
    return {part.strip().lower() for part in cookie.split(";")[1:]}


def notices(page: str) -> list[str]:
    return [text for attrs, text in elements(page, "p") if attrs.get("role") == "status"]


# The idle window


def test_a_refused_request_of_a_signed_in_person_still_counts_as_use(world: World):
    world.sign_in("Wen")
    world.clock.advance(minutes=20)
    assert world.send("GET", "/review", actor="Wen").status_code == 403

    world.clock.advance(minutes=20)
    world.responses.clear()
    world.send("GET", "/reports", actor="Wen")

    world.assert_accepted()


def test_a_request_that_resolves_nobody_does_not_extend_the_idle_window(world: World):
    world.sign_in("Wen")
    world.clock.advance(minutes=20)
    assert world.open_page("/no-such-page", actor="Wen").status_code == 404
    assert world.open_page("/static/htmx-2.0.4.min.js", actor="Wen").status_code == 200

    world.clock.advance(minutes=10)
    world.send("GET", "/reports", actor="Wen")

    world.assert_rejected("UNAUTHENTICATED", "請重新登入")


def test_a_timed_out_session_is_ended_and_stays_ended_when_the_clock_goes_back(world: World):
    world.sign_in("Wen")
    world.clock.advance(minutes=30)
    timed_out_at = world.clock.now()

    world.send("GET", "/reports", actor="Wen")
    world.send("GET", "/reports", actor="Wen")
    world.clock.advance(minutes=-30)
    world.send("GET", "/reports", actor="Wen")
    world.send("GET", "/", actor="Wen")

    *refused, front_door = world.responses
    world.responses[:] = refused
    world.assert_rejected("UNAUTHENTICATED", "請重新登入")
    assert front_door.headers["location"] == "/sign-in"
    [session] = world.changes()
    assert (session.table, session.kind, session.before["ended_at"]) == ("sessions", "changed", None)
    assert datetime.fromisoformat(session.after["ended_at"]) == timed_out_at


def test_two_sessions_of_one_person_time_out_independently(world: World):
    world.sign_in("Wen")
    world.sessions["Wen, first"] = world.sessions["Wen"]
    world.clock.advance(minutes=20)
    world.sign_in("Wen")

    world.clock.advance(minutes=10)
    first = world.send("GET", "/reports", actor="Wen, first")
    second = world.send("GET", "/reports", actor="Wen")

    assert (first.status_code, second.status_code) == (401, 200)

    world.clock.advance(minutes=29, seconds=59)
    assert world.send("GET", "/reports", actor="Wen").status_code == 200


# The cookie


@pytest.mark.parametrize(("app_env", "secure"), [("development", False), ("test", False), ("production", True)])
def test_the_cookie_lasts_for_the_browser_session_and_is_secure_only_in_production(world: World, settings, app_env, secure):
    there = dataclasses.replace(settings, app_env=app_env, password_hash_profile="standard")
    with TestClient(create_app(there, world.clock)) as client:
        response = client.post("/sign-in", data=WEN, follow_redirects=False)

    assert response.status_code == 303
    attributes = cookie_attributes(response)
    assert ("secure" in attributes) is secure
    assert attributes - {"secure"} == {"httponly", "samesite=lax", "path=/"}


# The anti-forgery token


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("carried", ["header", "form field"])
def test_the_sessions_token_is_accepted_from_the_header_or_the_form(world: World, method, carried):
    world.sign_in("Wen")
    token = world.csrf_token("Wen")
    how = {"headers": {CSRF_HEADER: token}} if carried == "header" else {"data": {CSRF_FIELD: token}}

    world.send(method, "/_test/change", actor="Wen", csrf=False, **how)

    world.assert_accepted()
    world.assert_nothing_written()


def carried_tokens(world: World) -> dict[str, dict]:
    other = world.csrf_token("Wei")
    return {
        "nothing": {},
        "an empty header": {"headers": {CSRF_HEADER: ""}},
        "a made-up header": {"headers": {CSRF_HEADER: "made-up"}},
        "another session's token in the header": {"headers": {CSRF_HEADER: other}},
        "another session's token in the form": {"data": {CSRF_FIELD: other}},
        "the token in a field of another name": {"data": {"token": world.csrf_token("Wen")}},
        "the token in the query": {"params": {CSRF_FIELD: world.csrf_token("Wen")}},
        "the token in a JSON body": {"json": {CSRF_FIELD: world.csrf_token("Wen")}},
    }


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "carried",
    [
        "nothing",
        "an empty header",
        "a made-up header",
        "another session's token in the header",
        "another session's token in the form",
        "the token in a field of another name",
        "the token in the query",
        "the token in a JSON body",
    ],
)
def test_a_change_without_the_sessions_own_token_is_forbidden_and_recorded_once(world: World, database_url, method, carried):
    world.sign_in("Wen")
    world.sign_in("Wei")

    world.send(method, "/_test/change", actor="Wen", csrf=False, **carried_tokens(world)[carried])

    world.assert_rejected("FORBIDDEN", "請求未通過驗證")
    world.assert_audit_rows_written("ACCESS_DENIED", actor="Wen")
    world.assert_nothing_else_written()
    with psycopg.connect(database_url) as conn:
        assert conn.execute("select description from audit_log").fetchone()[0] == f"請求未通過驗證：{method} /_test/change"


def test_a_request_that_changes_nothing_or_carries_no_session_needs_no_token(world: World):
    world.sign_in("Wen")

    world.send("GET", "/reports", actor="Wen")
    world.send("POST", "/_test/change")

    world.assert_accepted()
    world.assert_nothing_written()


def test_a_made_up_session_with_any_token_is_not_signed_in(world: World):
    world.sessions["Intruder"] = "not-a-token-anyone-was-given"

    world.send("POST", "/sign-out", actor="Intruder", headers={CSRF_HEADER: "made-up"})

    world.assert_rejected("UNAUTHENTICATED", "請重新登入")
    world.assert_nothing_written()


def test_signing_in_needs_no_token_even_with_a_session(world: World):
    world.sign_in("Wen")

    response = world.send("POST", "/sign-in", actor="Wen", csrf=False, data=WEN)

    assert response.status_code == 303
    assert response.cookies[SESSION_COOKIE] != world.sessions["Wen"]
    [session] = world.changes()
    assert (session.table, session.kind) == ("sessions", "added")


def test_signing_out_without_the_token_leaves_the_session_signed_in(world: World):
    world.sign_in("Wen")

    world.send("POST", "/sign-out", actor="Wen", csrf=False)

    world.assert_rejected("FORBIDDEN", "請求未通過驗證")
    assert world.open_page("/reports", actor="Wen").status_code == 200


def test_each_session_has_its_own_token_and_the_cookie_is_not_it(world: World, database_url):
    world.sign_in("Wen")
    first = world.csrf_token("Wen")
    first_cookie = world.sessions["Wen"]
    world.sign_in("Wen")
    world.sign_in("Wei")

    tokens = {first, world.csrf_token("Wen"), world.csrf_token("Wei")}

    assert len(tokens) == 3
    assert all(len(token) >= 32 for token in tokens)
    assert first != first_cookie


# The pages


def test_every_page_of_a_signed_in_person_carries_the_token_for_htmx_and_for_the_sign_out_form(world: World):
    world.sign_in("Wen")
    token = world.csrf_token("Wen")

    for path, status in [("/reports", 200), ("/review", 403)]:
        page = world.open_page(path, actor="Wen")

        assert page.status_code == status
        [body] = [attrs for attrs, _ in elements(page.text, "body")]
        assert json.loads(body["hx-headers"]) == {CSRF_HEADER: token}
        [form] = [attrs for attrs, _ in elements(page.text, "form")]
        assert (form["method"], form["action"]) == ("post", "/sign-out")
        [field] = [attrs for attrs, _ in elements(page.text, "input")]
        assert (field["type"], field["name"], field["value"]) == ("hidden", CSRF_FIELD, token)
        assert [text for _, text in elements(page.text, "button")] == ["登出"]


def test_a_visitors_page_carries_no_token_and_no_sign_out(world: World):
    page = world.open_page("/sign-in")

    [body] = [attrs for attrs, _ in elements(page.text, "body")]
    assert body == {}
    assert CSRF_FIELD not in page.text
    assert "/sign-out" not in page.text
    assert notices(page.text) == []


@pytest.mark.parametrize(("name", "landing"), [("Wen", "/reports"), ("Admin1", "/review"), ("Kuei", "/review")])
def test_the_sign_in_page_sends_a_signed_in_person_to_their_landing_page(world: World, name, landing):
    world.sign_in(name)

    response = world.send("GET", "/sign-in", actor=name)

    assert (response.status_code, response.headers["location"]) == (303, landing)


def test_a_refusal_page_is_titled_with_its_status(world: World):
    world.sign_in("Wen")

    response = world.send("GET", "/review", actor="Wen", headers=BROWSER)

    assert [text for _, text in elements(response.text, "title")] == ["403｜YC 日報系統"]


# Sign-out


def test_signing_out_with_the_pages_form_shows_the_sign_in_page_saying_so(world: World):
    world.sign_in("Wen")
    signed_out_at = world.clock.now()

    response = world.send(
        "POST", "/sign-out", actor="Wen", csrf=False, data={CSRF_FIELD: world.csrf_token("Wen")}, headers=BROWSER
    )

    assert response.status_code == 303
    # The browser is told to drop the cookie.
    assert response.headers["set-cookie"].startswith(f'{SESSION_COOKIE}="";')
    assert "max-age=0" in cookie_attributes(response)
    [session] = world.changes()
    assert (session.table, session.kind) == ("sessions", "changed")
    assert datetime.fromisoformat(session.after["ended_at"]) == signed_out_at

    shown = world.open_page(response.headers["location"])
    assert shown.status_code == 200
    assert notices(shown.text) == ["您已登出"]
    assert alert_texts(shown.text) == []
    assert [attrs["action"] for attrs, _ in elements(shown.text, "form")] == ["/sign-in"]
    assert "signed-in-as" not in shown.text


def test_the_old_cookie_after_sign_out_shows_the_sign_in_page_asking_to_sign_in_again(world: World):
    world.sign_in("Wen")
    world.send("POST", "/sign-out", actor="Wen")

    for method, path in [("GET", "/reports"), ("POST", "/sign-out")]:
        response = world.send(method, path, actor="Wen", headers=BROWSER)

        assert response.status_code == 401
        assert response.headers["X-Outcome"] == "UNAUTHENTICATED"
        assert alert_texts(response.text) == ["請重新登入"]
        assert notices(response.text) == []
        assert "signed-in-as" not in response.text
    assert world.send("GET", "/", actor="Wen").headers["location"] == "/sign-in"


def test_signing_out_ends_only_that_session(world: World):
    world.sign_in("Wen")
    world.sessions["Wen, elsewhere"] = world.sessions["Wen"]
    world.sign_in("Wen")
    world.sign_in("Wei")

    world.send("POST", "/sign-out", actor="Wen")

    assert world.open_page("/reports", actor="Wen").status_code == 401
    assert world.open_page("/reports", actor="Wen, elsewhere").status_code == 200
    assert world.open_page("/reports", actor="Wei").status_code == 200


def test_signing_out_needs_a_session(world: World):
    world.send("POST", "/sign-out")

    world.assert_rejected("UNAUTHENTICATED", "請重新登入")
    world.assert_nothing_written()


# The harness


def test_pytest_bdd_is_the_version_the_harness_was_built_against():
    pinned = f'"pytest-bdd=={version("pytest-bdd")}"'

    assert pinned in (REPO / "pyproject.toml").read_text(encoding="utf-8")
