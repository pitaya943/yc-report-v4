"""Runs every scenario under docs/spec, straight from the feature files.

A scenario runs when its rule is listed in tests/implemented_rules.txt;
otherwise it is skipped as not built yet (tests/conftest.py).
"""

from pytest_bdd import scenarios

from tests.steps import step_definitions

# pytest-bdd finds step definitions as fixtures of the module that holds the scenarios.
globals().update(step_definitions())

scenarios(".")
