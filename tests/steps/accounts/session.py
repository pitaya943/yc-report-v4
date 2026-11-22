"""Steps of IAM-F03 (session and sign-out)."""

import dataclasses
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from httpx2 import Response
from pytest_bdd import given, parsers, then, when

from app.core.config import Settings
from app.main import create_app
from tests.steps.accounts.sign_in import LANDING_PAGES
from tests.support import recorder
from tests.support.world import SESSION_COOKIE, World, outcome_statuses

IDLE_LIMIT_MINUTES = 30  # IAM-R10


def protected_page(world: World, name: str) -> str:
    """A page ``name`` may open and a visitor may not: the landing page of their role."""
    page = "daily report" if world.accounts[name]["role"] == "USER" else "confirmation"
    return LANDING_PAGES[page][0]


def cookie_attributes(response: Response) -> set[str]:
    """The attributes of the one cookie a response sets, in lower case."""
    [cookie] = response.headers.get_list("set-cookie")
    name, *attributes = (part.strip() for part in cookie.split(";"))
    assert name.startswith(f"{SESSION_COOKIE}=")
    return {attribute.lower() for attribute in attributes}


def assert_refused_as_unauthenticated(response: Response) -> None:
    assert response.status_code == outcome_statuses()["UNAUTHENTICATED"], response.text
    assert response.headers.get("X-Outcome") == "UNAUTHENTICATED"


# IAM-R10


@given(parsers.re(r'^"(?P<name>[^"]+)" signed in and last used the system (?P<minutes>\d+) min (?P<seconds>\d+) sec ago$'))
def signed_in_and_last_used_the_system(world: World, name: str, minutes: str, seconds: str):
    world.sign_in(name)
    world.clock.advance(minutes=int(minutes), seconds=int(seconds))


@given(
    parsers.re(
        r'^"(?P<name>[^"]+)" signed in (?P<since>\d+) minutes ago'
        r" and last used the system (?P<idle>\d+) minutes ago$"
    )
)
def signed_in_and_used_the_system_since(world: World, name: str, since: str, idle: str):
    world.sign_in(name)
    # The time up to the last use is itself longer than the idle limit, so the
    # person was using the system during it.
    until_last_use = int(since) - int(idle)
    while until_last_use:
        step = min(until_last_use, IDLE_LIMIT_MINUTES - 1)
        world.clock.advance(minutes=step)
        assert world.open_page(protected_page(world, name), actor=name).status_code == 200
        until_last_use -= step
    world.clock.advance(minutes=int(idle))


@when(parsers.re(r'^"(?P<name>[^"]+)" requests a protected action$'))
def requests_a_protected_action(world: World, name: str):
    world.send("GET", protected_page(world, name), actor=name)


@given(
    parsers.re(r'^"(?P<name>[^"]+)" saved a report and was then signed out for idle time$'),
    target_fixture="kept",
)
def saved_a_report_and_was_signed_out_for_idle_time(world: World, name: str) -> recorder.Snapshot:
    """Returns what the database held when the session timed out.

    Nothing can save a report yet. Until something can, the scenario is held
    to more than it says: a timeout removes and changes no stored row at all.
    """
    kept = recorder.snapshot(world.database_url)
    assert not [table for table in kept if "report" in table], (
        "reports are stored now: this step has to save a real one, and the Then step has to look for it"
    )
    world.sign_in(name)
    world.clock.advance(minutes=IDLE_LIMIT_MINUTES)
    assert_refused_as_unauthenticated(world.open_page(protected_page(world, name), actor=name))
    return kept


@then("the report is still there")
def the_report_is_still_there(world: World, kept: recorder.Snapshot):
    [response] = world.responses
    assert response.status_code == 303, response.text
    after = recorder.snapshot(world.database_url)
    lost = [change for change in recorder.diff(kept, after) if change.kind != "added"]
    assert lost == []
    # The timed-out session and the new one are both there; only the first has ended.
    sessions = sorted(after["sessions"].values(), key=lambda row: row["id"])
    assert [row["ended_at"] is not None for row in sessions] == [True, False]


@then(parsers.re(r"^no credential is issued that outlives the (?P<minutes>\d+)-minute idle window$"))
def no_credential_outlives_the_idle_window(world: World, minutes: str):
    [response] = world.responses
    assert response.status_code == 303, response.text
    # Nothing but the session cookie, and that one goes when the browser closes.
    attributes = cookie_attributes(response)
    assert not [attribute for attribute in attributes if attribute.startswith(("max-age", "expires"))], attributes
    assert set(response.cookies) == {SESSION_COOKIE}

    world.sessions["the credential"] = response.cookies[SESSION_COOKIE]
    [name] = [name for name, account in world.accounts.items() if name in response.request.content.decode()]
    world.clock.advance(minutes=int(minutes), seconds=-1)
    assert world.open_page(protected_page(world, name), actor="the credential").status_code == 200
    world.clock.advance(minutes=int(minutes))
    assert_refused_as_unauthenticated(world.open_page(protected_page(world, name), actor="the credential"))


# IAM-R11


@when(parsers.re(r'^"(?P<name>[^"]+)" signs out$'))
def signs_out(world: World, name: str):
    world.send("POST", "/sign-out", actor=name)


@then("a later protected request from that session is rejected as UNAUTHENTICATED")
def a_later_request_from_that_session_is_rejected(world: World):
    [signed_out] = world.responses
    assert signed_out.status_code == 303, signed_out.text
    [name] = world.sessions
    assert_refused_as_unauthenticated(world.send("GET", protected_page(world, name), actor=name))


@when(parsers.re(r'^"(?P<name>[^"]+)" opens the sign-in page$'))
def opens_the_sign_in_page(world: World, name: str):
    world.send("GET", "/sign-in", actor=name)


@then(parsers.re(rf'^"(?P<name>[^"]+)" is sent to the (?P<page>{"|".join(LANDING_PAGES)}) page$'))
def is_sent_to_the_page(world: World, name: str, page: str):
    [response] = world.responses
    assert response.status_code == 303, response.text
    assert urlsplit(response.headers["location"]).path == LANDING_PAGES[page][0]


# IAM-R12


@then("the session cookie is HttpOnly")
def the_session_cookie_is_http_only(world: World):
    [response] = world.responses
    assert "httponly" in cookie_attributes(response)


@then("its SameSite attribute is Lax or Strict")
def its_same_site_attribute_is_lax_or_strict(world: World):
    [response] = world.responses
    assert cookie_attributes(response) & {"samesite=lax", "samesite=strict"}


@then("it is Secure in production")
def it_is_secure_in_production(world: World, settings: Settings):
    """The same sign-in, sent to the application started with APP_ENV=production."""
    [response] = world.responses
    request = response.request
    production = dataclasses.replace(settings, app_env="production", password_hash_profile="standard")
    with TestClient(create_app(production, world.clock)) as client:
        there = client.post(
            request.url.path,
            content=request.content,
            headers={"Content-Type": request.headers["content-type"]},
            follow_redirects=False,
        )
    assert there.status_code == 303, there.text
    assert "secure" in cookie_attributes(there)


@when("a state-changing request arrives with the session but without a valid anti-forgery token")
def a_state_changing_request_arrives_without_a_token(world: World):
    [name] = world.sessions
    world.send("POST", "/sign-out", actor=name, csrf=False)
