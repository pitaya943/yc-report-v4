"""Steps of AUD-F01 (authorization on every action)."""

import re

from pytest_bdd import when

from tests.support.world import World

# The only paths a visitor may use. Every other route of the application is
# protected, including the ones later tasks add.
PUBLIC_PATHS = frozenset({"/", "/sign-in", "/sign-in/names", "/health"})


def protected_requests(app) -> list[tuple[str, str]]:
    """A (method, path) for every protected route, path parameters filled with ``1``.

    Read from the application's own description of its routes. Static files
    are not routes and are not listed.
    """
    return sorted(
        (method.upper(), re.sub(r"\{[^}]+\}", "1", path))
        for path, operations in app.openapi()["paths"].items()
        if path not in PUBLIC_PATHS
        for method in operations
    )


@when("a visitor requests any protected action")
def a_visitor_requests_any_protected_action(world: World):
    requests = protected_requests(world.client.app)
    assert requests, "the application has no protected route"
    for method, path in requests:
        world.send(method, path)
