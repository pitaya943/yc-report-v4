"""Steps shared by every area. Their meaning is fixed in README.md next to this file."""

from collections.abc import Callable

from pytest_bdd import given, parsers, then

from tests.support.world import World, outcome_statuses, parse_moment

# Area steps add the names of their own successes here, e.g. "signed in",
# each with the check that it happened.
SUCCESS_OUTCOMES: dict[str, Callable[[World], None]] = {"accepted": World.assert_accepted}

_ACTOR = r'(?: with actor (?P<actor>"[^"]*"|SYSTEM))?'


def _actor(text: str | None) -> str | None:
    return text.strip('"') if text else None


@given(parsers.re(r'^the clock is "(?P<moment>[^"]+)"(?: in Asia/Taipei)?$'))
def the_clock_is(world: World, moment: str):
    world.clock.set(parse_moment(moment))


@given(parsers.re(r'^"(?P<name>[^"]+)" is signed in$'))
def is_signed_in(world: World, name: str):
    world.sign_in(name)


@then(parsers.re(r'^the request is rejected as (?P<outcome>[A-Z_]+)(?: with message "(?P<message>.*)")?$'))
def the_request_is_rejected(world: World, outcome: str, message: str | None):
    world.assert_rejected(outcome, message)


@then(parsers.re(r'^the outcome is (?P<outcome>.+?)(?: with message "(?P<message>.*)")?$'))
def the_outcome_is(world: World, outcome: str, message: str | None):
    if outcome in outcome_statuses():
        world.assert_rejected(outcome, message)
    elif outcome in SUCCESS_OUTCOMES:
        assert not message, "a success has no message to compare"
        SUCCESS_OUTCOMES[outcome](world)
    else:
        raise AssertionError(f"no area has said what the outcome {outcome!r} means")


@then("nothing is written")
def nothing_is_written(world: World):
    world.assert_nothing_written()


@then("no audit row is written")
def no_audit_row_is_written(world: World):
    world.assert_no_audit_row_written()


@then(parsers.re(rf'^an audit row "(?P<type>[A-Z_]+)" is written{_ACTOR}$'))
def an_audit_row_is_written(world: World, type: str, actor: str | None):
    world.assert_audit_rows_written(type, actor=_actor(actor))


@then(parsers.re(rf'^exactly (?P<count>\d+) audit rows? "(?P<type>[A-Z_]+)" (?:is|are) written{_ACTOR}$'))
def exactly_n_audit_rows_are_written(world: World, count: str, type: str, actor: str | None):
    world.assert_audit_rows_written(type, actor=_actor(actor), count=int(count))


@then(parsers.re(r'^audit rows "(?P<first>[A-Z_]+)" and "(?P<second>[A-Z_]+)" are written$'))
def two_audit_rows_are_written(world: World, first: str, second: str):
    world.assert_audit_rows_written(first)
    world.assert_audit_rows_written(second)


@then("nothing else is written")
def nothing_else_is_written(world: World):
    world.assert_nothing_else_written()


@then(parsers.re(rf'^nothing is written except an audit row "(?P<type>[A-Z_]+)"{_ACTOR}$'))
def nothing_is_written_except_an_audit_row(world: World, type: str, actor: str | None):
    world.assert_audit_rows_written(type, actor=_actor(actor))
    world.assert_nothing_else_written()

