"""Lockout and rate-limit details the spec's scenarios do not pin down (design section 9.2)."""

from datetime import datetime, timedelta

import random
import string

import argon2
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.main import create_app
from tests.support.together import run_together
from tests.support.world import PASSWORD, World

JSON = {"Accept": "application/json"}
TOO_MANY_ATTEMPTS = "登入嘗試過於頻繁，請稍後再試"
LOCKED = "密碼錯誤次數過多，請在 15 分鐘後再試"


def wrong_password(world: World, name: str = "Wen"):
    return world.prepare("POST", "/sign-in", data={"name": name, "password": "wrong"})


def lock(world: World, name: str = "Wen") -> None:
    assert [wrong_password(world, name).status_code for _ in range(5)] == [401, 401, 401, 401, 423]


def use_up_the_address(world: World) -> None:
    for _ in range(10):
        assert wrong_password(world, "Nobody").status_code == 401


def account_changes(world: World) -> list[dict]:
    return [change.after for change in world.changes() if change.table == "accounts"]


def attempts_added(world: World) -> int:
    return len([change for change in world.changes() if change.table == "sign_in_attempts" and change.kind == "added"])


# The rate limit


def test_a_rate_limited_attempt_is_not_recorded_and_touches_no_account(world: World):
    use_up_the_address(world)

    world.send("POST", "/sign-in", data={"name": "Wen", "password": "wrong"})
    world.send("POST", "/sign-in", data={"name": "Wen", "password": PASSWORD})

    world.assert_rejected("RATE_LIMITED", TOO_MANY_ATTEMPTS)
    world.assert_nothing_written()


def test_an_attempt_stops_counting_once_it_is_60_seconds_old(world: World):
    wrong_password(world, "Nobody")
    world.clock.advance(seconds=1)
    for _ in range(9):
        wrong_password(world, "Nobody")
    world.clock.advance(seconds=58)

    world.send("POST", "/sign-in", data={"name": "Wen", "password": PASSWORD})
    world.assert_rejected("RATE_LIMITED")

    # 60 seconds after the first attempt: it no longer counts, the other nine do.
    world.clock.advance(seconds=1)
    assert world.send("POST", "/sign-in", data={"name": "Wen", "password": PASSWORD}).status_code == 303
    world.send("POST", "/sign-in", data={"name": "Wen", "password": PASSWORD})
    assert [response.status_code for response in world.responses] == [429, 303, 429]


@pytest.mark.parametrize("name", ["Nobody", "Old"])
def test_a_failure_for_an_unknown_or_archived_name_changes_no_account_and_counts_toward_the_limit(world: World, name):
    for _ in range(10):
        world.send("POST", "/sign-in", data={"name": name, "password": PASSWORD})

    world.assert_rejected("UNAUTHENTICATED", "密碼錯誤，請重試")
    assert account_changes(world) == []
    assert attempts_added(world) == 10
    assert wrong_password(world, name).status_code == 429


def test_a_refused_form_is_not_an_attempt(world: World):
    for _ in range(11):
        world.send("POST", "/sign-in", data={"group": "west", "password": PASSWORD})

    world.assert_rejected("INVALID", "請選擇帳戶")
    world.assert_nothing_written()


@pytest.mark.parametrize(
    ("hops", "forwarded", "address"),
    [
        ("0", None, "testclient"),
        ("0", "198.51.100.1", "testclient"),
        ("1", "198.51.100.1", "198.51.100.1"),
        ("1", "6.6.6.6, 198.51.100.1", "198.51.100.1"),
        ("1", "6.6.6.6,198.51.100.1 ", "198.51.100.1"),
        ("2", "6.6.6.6, 198.51.100.1, 10.0.0.1", "198.51.100.1"),
        # Fewer proxies than expected: the request is counted under its peer.
        ("1", None, "testclient"),
        ("2", "198.51.100.1", "testclient"),
        # The header sent as several lines is one list.
        ("2", ["6.6.6.6, 198.51.100.1", "10.0.0.1"], "198.51.100.1"),
        ("1", ["198.51.100.1", "6.6.6.6", "203.0.113.9"], "203.0.113.9"),
        ("1", "2001:DB8::1", "2001:db8::1"),
        # Not an address: no proxy wrote it, so the request is counted under its peer.
        ("1", "not-an-address", "testclient"),
        ("1", "fe80::1%" + "z" * 9000, "testclient"),
    ],
)
def test_the_client_address_is_the_peer_or_the_value_the_trusted_proxy_wrote(
    world: World, database_url, hops, forwarded, address
):
    settings = load_settings(
        {"DATABASE_URL": database_url, "APP_ENV": "test", "PASSWORD_HASH_PROFILE": "fast", "TRUSTED_PROXY_HOPS": hops}
    )
    lines = [forwarded] if isinstance(forwarded, str) else forwarded or []
    headers = [*JSON.items(), *(("X-Forwarded-For", line) for line in lines)]

    with TestClient(create_app(settings, world.clock)) as client:
        client.post("/sign-in", data={"name": "Wen", "password": "wrong"}, headers=headers)

    with psycopg.connect(database_url) as conn:
        assert conn.execute("select client_address from sign_in_attempts").fetchall() == [(address,)]


def test_a_forwarded_value_too_long_to_be_an_address_is_answered_as_usual(world: World, database_url):
    settings = load_settings(
        {"DATABASE_URL": database_url, "APP_ENV": "test", "PASSWORD_HASH_PROFILE": "fast", "TRUSTED_PROXY_HOPS": "1"}
    )
    noise = "".join(random.Random(9).choices(string.ascii_letters + string.digits, k=9000))

    with TestClient(create_app(settings, world.clock), raise_server_exceptions=False) as client:
        wrong = client.post("/sign-in", data={"name": "Wen", "password": "wrong"}, headers=JSON | {"X-Forwarded-For": noise})
        right = client.post(
            "/sign-in",
            data={"name": "Wen", "password": PASSWORD},
            headers=JSON | {"X-Forwarded-For": noise},
            follow_redirects=False,
        )

    assert (wrong.status_code, wrong.json()["message"]) == (401, "密碼錯誤，請重試")
    assert right.status_code == 303
    with psycopg.connect(database_url) as conn:
        assert conn.execute("select max(length(client_address)) <= 45 from sign_in_attempts").fetchone() == (True,)


def test_a_forwarded_address_the_client_made_up_does_not_escape_the_limit(world: World):
    for i in range(10):
        world.prepare("POST", "/sign-in", data={"name": "Nobody", "password": "any"}, headers={"X-Forwarded-For": f"6.6.6.{i}"})

    world.send("POST", "/sign-in", data={"name": "Wen", "password": PASSWORD}, headers={"X-Forwarded-For": "6.6.6.66"})

    world.assert_rejected("RATE_LIMITED", TOO_MANY_ATTEMPTS)


# The lock


def test_the_failure_count_survives_the_refusal(world: World):
    world.send("POST", "/sign-in", data={"name": "Wen", "password": "wrong"})

    world.assert_rejected("UNAUTHENTICATED", "密碼錯誤，請重試")
    [account] = account_changes(world)
    assert (account["display_name"], account["failed_count"], account["locked_until"]) == ("Wen", 1, None)
    assert datetime.fromisoformat(account["last_failed_at"]) == world.clock.now()
    assert attempts_added(world) == 1


def test_the_fifth_failure_writes_the_lock_and_one_lockout_row(world: World):
    for _ in range(4):
        wrong_password(world)

    world.send("POST", "/sign-in", data={"name": "Wen", "password": "wrong"})

    world.assert_rejected("LOCKED", LOCKED)
    [account] = account_changes(world)
    assert account["failed_count"] == 5
    assert datetime.fromisoformat(account["locked_until"]) == world.clock.now() + timedelta(minutes=15)
    world.assert_audit_rows_written("ACCOUNT_LOCKOUT", actor="SYSTEM")
    [row] = [change.after for change in world.changes() if change.table == "audit_log"]
    assert "Wen" in row["description"]
    assert attempts_added(world) == 1


def test_an_attempt_during_a_lock_checks_no_password_counts_no_failure_and_does_not_extend_the_lock(
    world: World, monkeypatch
):
    lock(world)
    verified: list[str] = []
    verify = argon2.PasswordHasher.verify

    def counting(hasher, hash, password):
        verified.append(hash)
        return verify(hasher, hash, password)

    monkeypatch.setattr(argon2.PasswordHasher, "verify", counting)

    world.clock.advance(minutes=10)
    world.send("POST", "/sign-in", data={"name": "Wen", "password": "wrong"})
    world.send("POST", "/sign-in", data={"name": "Wen", "password": PASSWORD})

    world.assert_rejected("LOCKED", LOCKED)
    assert verified == []
    assert account_changes(world) == []
    world.assert_no_audit_row_written()
    # It still counts toward the address's rate limit.
    assert attempts_added(world) == 2

    # 15 minutes after the lock began, not after the last attempt.
    world.clock.advance(minutes=5)
    assert world.prepare("POST", "/sign-in", data={"name": "Wen", "password": PASSWORD}).status_code == 303


def test_two_wrong_passwords_at_the_same_instant_make_one_lock_and_one_lockout_row(world: World, app, database_url):
    for _ in range(4):
        wrong_password(world)

    def attempt(address: str):
        # A different address each, so only the account itself can make one wait for the other.
        # The application is already running for ``world``; this is one more client of it.
        client = TestClient(app, client=(address, 50000))
        return lambda: client.post("/sign-in", data={"name": "Wen", "password": "wrong"}, headers=JSON)

    responses = run_together(database_url, "audit_log", [attempt("198.51.100.1"), attempt("198.51.100.2")])

    assert [response.status_code for response in responses] == [423, 423]
    with psycopg.connect(database_url) as conn:
        assert conn.execute("select count(*) from audit_log where type = 'ACCOUNT_LOCKOUT'").fetchone() == (1,)
        assert conn.execute("select failed_count from accounts where display_name = 'Wen'").fetchone() == (5,)
        addresses = conn.execute("select client_address from sign_in_attempts order by id desc limit 2").fetchall()
        assert sorted(addresses) == [("198.51.100.1",), ("198.51.100.2",)]


# Fields


@pytest.mark.parametrize(
    ("form", "outcome", "message"),
    [
        ({"name": "Wen\x00"}, "INVALID", "請選擇帳戶"),
        ({"name": "\x00"}, "INVALID", "請選擇帳戶"),
        ({"group": "west", "name": "W\x00en"}, "INVALID", "請選擇帳戶"),
        ({"group": "west\x00", "name": "Wen"}, "INVALID", "請選擇類型"),
    ],
)
def test_a_nul_byte_in_the_name_or_the_group_is_invalid_and_writes_nothing(world: World, form, outcome, message):
    world.send("POST", "/sign-in", data={"password": PASSWORD, **form})

    world.assert_rejected(outcome, message)
    world.assert_nothing_written()


def test_a_nul_byte_in_the_password_is_a_wrong_password(world: World):
    world.send("POST", "/sign-in", data={"name": "Wen", "password": PASSWORD + "\x00"})
    world.send("POST", "/sign-in", data={"name": "Nobody", "password": "\x00"})

    world.assert_rejected("UNAUTHENTICATED", "密碼錯誤，請重試")
