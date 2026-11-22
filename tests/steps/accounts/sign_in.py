"""Steps of IAM-F01 (sign-in)."""

from urllib.parse import urlsplit

from pytest_bdd import parsers, then, when

from tests.support.html import elements
from tests.support.world import PASSWORD, SESSION_COOKIE, World, sign_in_group

# The page each landing is (design 9.1) and the heading it carries.
LANDING_PAGES = {"daily report": ("/reports", "日報"), "confirmation": ("/review", "確認")}


def _listed_names(world: World) -> list[str]:
    [response] = world.responses
    assert response.status_code == 200, response.text
    return [attrs["value"] for attrs, _ in elements(response.text, "option") if attrs["value"]]


@when(parsers.re(r'^a visitor chooses group "(?P<group>[^"]*)"$'))
def a_visitor_chooses_group(world: World, group: str):
    world.send("GET", "/sign-in/names", params={"group": group})


@then(parsers.re(r'^the name list is exactly "(?P<names>[^"]*)"$'))
def the_name_list_is_exactly(world: World, names: str):
    assert _listed_names(world) == names.split(", ")


@then(parsers.re(r'^the name list includes "(?P<name>[^"]*)"$'))
def the_name_list_includes(world: World, name: str):
    assert name in _listed_names(world)


@when(parsers.re(r'^"(?P<name>[^"]+)" signs in with the correct password$'))
def signs_in_with_the_correct_password(world: World, name: str):
    form = {"group": sign_in_group(world.accounts[name]), "name": name, "password": PASSWORD}
    world.send("POST", "/sign-in", data=form)


@when(parsers.re(r'^a visitor signs in as "(?P<name>[^"]*)" with "(?P<password>[^"]*)"$'))
def a_visitor_signs_in_as(world: World, name: str, password: str):
    # No group: with one, a name that is not on its list is refused for that
    # instead (appendix B, 登入帳戶), and this is about the password check.
    world.send("POST", "/sign-in", data={"name": name, "password": PASSWORD if password == "correct" else password})


@then(parsers.re(r'^"(?P<name>[^"]+)" is signed in$'))
def the_person_is_signed_in(world: World, name: str):
    [response] = world.responses
    assert response.status_code == 303, response.text
    world.sessions[name] = response.cookies[SESSION_COOKIE]
    page = world.open_page(response.headers["location"], actor=name)
    assert page.status_code == 200
    [shown] = [text for attrs, text in elements(page.text, "span") if attrs.get("id") == "signed-in-as"]
    assert shown.startswith(f"{name}（")


@then(parsers.re(r'^the landing page is "(?P<page>[^"]+)"$'))
def the_landing_page_is(world: World, page: str):
    path, heading = LANDING_PAGES[page]
    [response] = world.responses
    assert urlsplit(response.headers["location"]).path == path
    [actor] = [name for name, token in world.sessions.items() if token == response.cookies[SESSION_COOKIE]]
    landed = world.open_page(path, actor=actor)
    assert landed.status_code == 200
    assert [text for _, text in elements(landed.text, "h1")] == [heading]


@then("nobody is signed in")
def nobody_is_signed_in(world: World):
    for response in world.responses:
        assert SESSION_COOKIE not in response.cookies
    assert [change for change in world.changes() if change.table == "sessions"] == []
