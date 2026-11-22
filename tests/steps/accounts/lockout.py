"""Steps of IAM-F02 (sign-in lockout and rate limit)."""

import re
from contextlib import ExitStack
from datetime import datetime

import psycopg
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, then, when

from app.main import create_app
from tests.steps.common.steps import SUCCESS_OUTCOMES
from tests.support.together import run_together
from tests.support.world import PASSWORD, SESSION_COOKIE, World, outcome_statuses, sign_in_group

JSON = {"Accept": "application/json"}


def _fail_sign_in(world: World, name: str) -> int:
    """One wrong password for ``name``, as part of setting the scene; the status that came back."""
    return world.prepare("POST", "/sign-in", data={"name": name, "password": "wrong"}).status_code


def _lock(world: World, name: str) -> None:
    statuses = [_fail_sign_in(world, name) for _ in range(5)]
    assert statuses == [401, 401, 401, 401, 423], statuses


def _failure_state(world: World, name: str) -> tuple[int, datetime | None]:
    with psycopg.connect(world.database_url) as conn:
        return conn.execute(
            "select failed_count, locked_until from accounts where display_name = %s", (name,)
        ).fetchone()


def _signed_in(world: World) -> None:
    assert world.responses, "no request was sent"
    for response in world.responses:
        assert response.status_code == 303, f"status {response.status_code} {response.text}"
        assert response.cookies.get(SESSION_COOKIE)
    assert [change.kind for change in world.changes() if change.table == "sessions"] == ["added"] * len(world.responses)


SUCCESS_OUTCOMES["signed in"] = _signed_in


@given(parsers.re(r'^"(?P<name>[^"]+)" has (?P<count>\d+) failed sign-ins in the last 15 minutes$'))
def has_failed_sign_ins_in_the_last_15_minutes(world: World, name: str, count: str):
    for _ in range(int(count)):
        assert _fail_sign_in(world, name) == 401
        world.clock.advance(minutes=1)


@given(parsers.re(r'^"(?P<name>[^"]+)" has (?P<count>\d+) failed sign-ins$'))
def has_failed_sign_ins(world: World, name: str, count: str):
    for _ in range(int(count)):
        _fail_sign_in(world, name)
    assert _failure_state(world, name)[0] == int(count)


@given(parsers.re(r'^"(?P<name>[^"]+)" has 5 failed sign-ins and is locked$'))
def has_5_failed_sign_ins_and_is_locked(world: World, name: str):
    _lock(world, name)


@given(parsers.re(r'^"(?P<name>[^"]+)" was locked (?P<elapsed>.+) ago$'))
def was_locked_some_time_ago(world: World, name: str, elapsed: str):
    match = re.fullmatch(r"(\d+) min(?:utes)?(?: (\d+) sec)?", elapsed)
    assert match, f"not a time this step understands: {elapsed}"
    _lock(world, name)
    world.clock.advance(minutes=int(match.group(1)), seconds=int(match.group(2) or 0))


@given(parsers.re(r'^"(?P<name>[^"]+)" then signed in successfully$'))
def then_signed_in_successfully(world: World, name: str):
    form = {"group": sign_in_group(world.accounts[name]), "name": name, "password": PASSWORD}
    assert world.prepare("POST", "/sign-in", data=form).status_code == 303


@given("the 15-minute lock has ended")
@given("15 minutes passed with no further failure")
def fifteen_minutes_passed(world: World):
    world.clock.advance(minutes=15)


@when(parsers.re(r'^"(?P<name>[^"]+)" signs in with a wrong password$'))
def signs_in_with_a_wrong_password(world: World, name: str):
    world.send("POST", "/sign-in", data={"name": name, "password": "wrong"})


@then(parsers.re(r'^the failure count for "(?P<name>[^"]+)" is (?P<count>\d+)$'))
def the_failure_count_is(world: World, name: str, count: str):
    assert _failure_state(world, name)[0] == int(count)


@then(parsers.re(r'^"(?P<name>[^"]+)" is not locked$'))
def is_not_locked(world: World, name: str):
    locked_until = _failure_state(world, name)[1]
    assert locked_until is None or locked_until <= world.clock.now()


@given(parsers.re(r"^one client address has made (?P<count>\d+) sign-in attempts in the last 60 seconds$"))
def one_address_has_made_attempts(world: World, count: str):
    # Spread over 50 of the 60 seconds, and for nobody's account: an attempt
    # counts whoever it is for.
    for _ in range(int(count)):
        assert world.prepare("POST", "/sign-in", data={"name": "Nobody", "password": "any"}).status_code == 401
        world.clock.advance(seconds=5)


@when("that address attempts another sign-in with a correct password")
def that_address_attempts_another_sign_in(world: World):
    world.send("POST", "/sign-in", data={"name": "Wen", "password": PASSWORD})


@given(parsers.re(r"^(?P<count>\d+) workers serve sign-in$"), target_fixture="workers")
def workers_serve_sign_in(world: World, request: pytest.FixtureRequest, count: str) -> list[TestClient]:
    """Each worker is an application of its own, with its own connections to the one database."""
    settings = world.client.app.state.settings
    running = ExitStack()
    request.addfinalizer(running.close)
    return [
        running.enter_context(TestClient(create_app(settings, world.clock), raise_server_exceptions=False))
        for _ in range(int(count))
    ]


@when(parsers.re(r"^one client address makes (?P<count>\d+) attempts in 60 seconds spread over both workers$"))
def one_address_makes_attempts_over_both_workers(world: World, workers: list[TestClient], count: str):
    """All the attempts are in flight at the same moment, alternating between the workers."""

    def attempt(worker: TestClient):
        return lambda: worker.post("/sign-in", data={"name": "Nobody", "password": "any"}, headers=JSON)

    calls = [attempt(workers[i % len(workers)]) for i in range(int(count))]
    world.responses += run_together(world.database_url, "sign_in_attempts", calls)


@then(parsers.re(r"^exactly (?P<count>\d+) attempts are evaluated$"))
def exactly_n_attempts_are_evaluated(world: World, count: str):
    limited = outcome_statuses()["RATE_LIMITED"]
    evaluated = [response for response in world.responses if response.status_code != limited]
    assert len(evaluated) == int(count), [response.status_code for response in world.responses]
    assert {response.status_code for response in evaluated} == {401}
    with psycopg.connect(world.database_url) as conn:
        assert conn.execute("select count(*) from sign_in_attempts").fetchone() == (int(count),)
