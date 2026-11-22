"""Sign-in details the spec's scenarios do not pin down, and the pages a person sees."""

import json
import re
from datetime import datetime

import argon2
import psycopg
import pytest

from app.accounts import service
from tests.steps.audit.authorization import protected_requests
from tests.support import recorder
from tests.support.html import alert_texts, elements
from tests.support.world import PASSWORD, SESSION_COOKIE, World

BROWSER = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}


def sign_in(world: World, **form: str):
    return world.send("POST", "/sign-in", data=form)


def page(world: World, path: str, *, actor: str | None = None):
    return world.open_page(path, actor=actor)


# Fields


@pytest.mark.parametrize("group", ["north", "ADMIN", "", " west"])
def test_an_unrecognised_group_is_invalid(world: World, group):
    sign_in(world, group=group, name="Wen", password=PASSWORD)
    world.send("GET", "/sign-in/names", params={"group": group})

    world.assert_rejected("INVALID", "請選擇類型")
    world.assert_nothing_written()


def test_the_name_list_needs_a_group(world: World):
    world.send("GET", "/sign-in/names")

    world.assert_rejected("INVALID", "請選擇類型")


@pytest.mark.parametrize(
    "form",
    [
        {"group": "west"},
        {"group": "west", "name": ""},
        {},
        {"group": "south", "name": "Wen"},  # a real account of another group
        {"group": "admin", "name": "Wen"},
        {"group": "west", "name": "Kuei"},
        {"group": "west", "name": "Old"},  # archived, so not on the list
        {"group": "west", "name": "Nobody"},
    ],
)
def test_a_missing_name_or_one_not_on_the_groups_list_is_invalid(world: World, form):
    sign_in(world, **form, password=PASSWORD)

    world.assert_rejected("INVALID", "請選擇帳戶")
    world.assert_nothing_written()


def test_a_missing_password_is_a_wrong_password(world: World):
    sign_in(world, group="west", name="Wen")

    world.assert_rejected("UNAUTHENTICATED", "密碼錯誤，請重試")
    # Counted like any other wrong password (tests/unit/test_sign_in_lockout.py).
    assert [change.table for change in world.changes()] == ["accounts", "sign_in_attempts"]


# Secrets


def test_the_database_never_holds_the_password_or_the_session_token(world: World, database_url):
    response = sign_in(world, group="west", name="Wen", password=PASSWORD)
    token = response.cookies[SESSION_COOKIE]

    [session] = [change for change in world.changes() if change.table == "sessions"]
    assert (session.table, session.kind) == ("sessions", "added")
    assert session.after["account_id"] == world.accounts["Wen"]["id"]
    assert datetime.fromisoformat(session.after["created_at"]) == world.clock.now()
    assert session.after["ended_at"] is None
    everything = json.dumps(recorder.snapshot(database_url), ensure_ascii=False)
    assert len(token) >= 32
    assert token not in everything
    assert PASSWORD not in everything


def test_each_sign_in_gets_its_own_token(world: World):
    tokens = {sign_in(world, group="west", name="Wen", password=PASSWORD).cookies[SESSION_COOKIE] for _ in range(3)}

    assert len(tokens) == 3


def test_an_unknown_or_archived_name_costs_a_password_verification_like_a_real_one(world: World, monkeypatch):
    verified: list[str] = []
    verify = argon2.PasswordHasher.verify

    def counting(hasher, hash, password):
        verified.append(hash)
        return verify(hasher, hash, password)

    monkeypatch.setattr(argon2.PasswordHasher, "verify", counting)

    for name, password in [("Wen", "wrong"), ("Nobody", "any"), ("Old", PASSWORD)]:
        verified.clear()
        sign_in(world, name=name, password=password)
        assert len(verified) == 1, name
        # The same kind of hash with the same cost as a real account's.
        assert re.sub(r"\$[^$]+\$[^$]+$", "", verified[0]) == "$argon2id$v=19$m=8,t=1,p=1", name

    world.assert_rejected("UNAUTHENTICATED", "密碼錯誤，請重試")


# Pages by role


@pytest.mark.parametrize(
    ("name", "wrong_page", "action"),
    [("Wen", "/review", "review.open"), ("Admin1", "/reports", "reports.open"), ("Kuei", "/reports", "reports.open")],
)
def test_the_other_roles_page_is_forbidden_and_recorded_once(world: World, database_url, name, wrong_page, action):
    world.sign_in(name)

    world.send("GET", wrong_page, actor=name)

    world.assert_rejected("FORBIDDEN", "禁止存取")
    world.assert_audit_rows_written("ACCESS_DENIED", actor=name)
    world.assert_nothing_else_written()
    with psycopg.connect(database_url) as conn:
        assert action in conn.execute("select description from audit_log").fetchone()[0]


@pytest.mark.parametrize(
    ("name", "path", "heading", "shown_as"),
    [
        ("Wen", "/reports", "日報", "Wen（員工）"),
        ("Admin1", "/review", "確認", "Admin1（管理員）"),
        ("Kuei", "/review", "確認", "Kuei（擁有者）"),
    ],
)
def test_the_landing_page_is_a_placeholder_showing_who_is_signed_in(world: World, name, path, heading, shown_as):
    world.sign_in(name)

    landed = page(world, path, actor=name)

    assert landed.status_code == 200
    assert 'lang="zh-Hant"' in landed.text
    assert [text for _, text in elements(landed.text, "h1")] == [heading]
    assert "這個頁面尚未建置" in landed.text
    assert [text for attrs, text in elements(landed.text, "span") if attrs.get("id") == "signed-in-as"] == [shown_as]


@pytest.mark.parametrize(("name", "landing"), [(None, "/sign-in"), ("Wen", "/reports"), ("Admin2", "/review"), ("Kuei", "/review")])
def test_the_front_door_leads_to_the_sign_in_page_or_the_landing_page(world: World, name, landing):
    if name:
        world.sign_in(name)

    response = world.send("GET", "/", actor=name)

    assert response.status_code == 303
    assert response.headers["location"] == landing


# The sign-in page


def test_the_sign_in_page_offers_the_three_groups_a_name_and_a_password(world: World):
    shown = page(world, "/sign-in")

    assert shown.status_code == 200
    assert alert_texts(shown.text) == []
    [form] = [attrs for attrs, _ in elements(shown.text, "form")]
    assert (form["method"], form["action"]) == ("post", "/sign-in")
    # Values and labels of appendix B, 登入群組.
    assert [(attrs["value"], text) for attrs, text in elements(shown.text, "option")] == [
        ("", "請選擇類型"),
        ("admin", "管理員"),
        ("west", "西區"),
        ("south", "南區"),
        ("", "請選擇帳戶"),
    ]
    selects = {attrs["name"]: attrs for attrs, _ in elements(shown.text, "select")}
    assert selects["group"]["hx-get"] == "/sign-in/names"
    assert selects["group"]["hx-target"] == "#" + selects["name"]["id"]
    assert [attrs["name"] for attrs, _ in elements(shown.text, "input")] == ["password"]
    assert "signed-in-as" not in shown.text


def test_the_page_script_is_the_pinned_htmx_and_is_served(world: World):
    shown = page(world, "/sign-in")

    [script] = [attrs for attrs, _ in elements(shown.text, "script")]
    # The integrity value htmx publishes for 2.0.4.
    assert script["integrity"] == "sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+"
    assert script["src"] == "/static/htmx-2.0.4.min.js"
    assert page(world, script["src"]).status_code == 200


def test_a_wrong_password_in_the_browser_shows_the_sign_in_page_again_with_the_message(world: World):
    response = world.send("POST", "/sign-in", data={"group": "west", "name": "Wen", "password": "wrong"}, headers=BROWSER)

    assert response.status_code == 401
    assert alert_texts(response.text) == ["密碼錯誤，請重試"]
    assert [attrs["action"] for attrs, _ in elements(response.text, "form")] == ["/sign-in"]


def test_other_refusals_in_the_browser_are_a_page_in_the_shared_layout(world: World):
    world.sign_in("Wen")

    response = world.send("GET", "/review", actor="Wen", headers=BROWSER)

    assert response.status_code == 403
    assert alert_texts(response.text) == ["禁止存取"]
    assert [text for attrs, text in elements(response.text, "span") if attrs.get("id") == "signed-in-as"] == ["Wen（員工）"]


# Sessions


@pytest.mark.parametrize("path", ["/reports", "/review"])
def test_a_protected_page_without_a_session_shows_the_sign_in_page_and_records_nothing(world: World, path):
    response = world.send("GET", path, headers=BROWSER)

    assert response.status_code == 401
    assert response.headers["X-Outcome"] == "UNAUTHENTICATED"
    assert alert_texts(response.text) == ["請重新登入"]
    assert [attrs["action"] for attrs, _ in elements(response.text, "form")] == ["/sign-in"]
    world.assert_nothing_written()


def test_the_session_cookie_is_kept_from_scripts_and_from_other_sites(world: World):
    response = sign_in(world, group="west", name="Wen", password=PASSWORD)

    attributes = {part.strip().lower() for part in response.headers["set-cookie"].split(";")[1:]}
    assert {"httponly", "samesite=lax", "path=/"} <= attributes


@pytest.mark.parametrize(
    "spoil",
    [
        "update sessions set ended_at = '2026-11-15T10:00:00+08:00'",
        "update accounts set archived_at = '2026-11-15T10:00:00+08:00' where display_name = 'Wen'",
    ],
)
def test_an_ended_session_or_one_of_an_archived_account_is_not_signed_in(world: World, database_url, spoil):
    world.sign_in("Wen")
    assert page(world, "/reports", actor="Wen").status_code == 200
    with psycopg.connect(database_url) as conn:
        conn.execute(spoil)

    world.send("GET", "/reports", actor="Wen")

    world.assert_rejected("UNAUTHENTICATED", "請重新登入")
    world.assert_nothing_written()


def test_a_made_up_session_cookie_is_not_signed_in(world: World):
    world.sign_in("Wen")
    world.sessions["Intruder"] = "not-a-token-anyone-was-given"

    world.send("GET", "/reports", actor="Intruder")

    world.assert_rejected("UNAUTHENTICATED", "請重新登入")


# The step behind AUD-R01


def test_any_protected_action_means_every_route_except_the_public_ones(app, world: World):
    @app.post("/_test/things/{thing_id}/parts/{part_id}")
    def change_part(thing_id: int, part_id: int):
        return {}

    assert protected_requests(app) == [
        ("GET", "/reports"),
        ("GET", "/review"),
        ("GET", "/status"),
        ("POST", "/_test/things/1/parts/1"),
        ("POST", "/sign-out"),
    ]


# The sign-in groups have one owner


def test_every_group_the_picker_offers_has_a_name_list(world: World, monkeypatch):
    monkeypatch.setitem(service.GROUPS, "office", service.Group("辦公室", roles=("ADMIN",), zone="SOUTH"))

    shown = page(world, "/sign-in")
    offered = [attrs["value"] for attrs, _ in elements(shown.text, "option") if attrs["value"]]
    assert offered == ["admin", "west", "south", "office"]
    for group in offered:
        assert world.send("GET", "/sign-in/names", params={"group": group}).status_code == 200
