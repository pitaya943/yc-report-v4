"""Step definitions for the spec's feature files: common/ for every area, one package per area."""

import importlib
import pkgutil

_STEP_DEFINITION = "pytestbdd_stepdef"


def step_definitions() -> dict[str, object]:
    """Import every module under tests/steps and return the step definitions they hold.

    pytest-bdd names a definition after its keyword and pattern, so the same
    pattern defined in two modules is found here, before it can shadow anything.
    """
    found: dict[str, object] = {}
    owner: dict[str, str] = {}
    for info in pkgutil.walk_packages(__path__, prefix=f"{__name__}."):
        module = importlib.import_module(info.name)
        for name, value in vars(module).items():
            if not name.startswith(_STEP_DEFINITION):
                continue
            if name in found:
                raise RuntimeError(f"the step {name!r} is defined in both {owner[name]} and {info.name}")
            found[name], owner[name] = value, info.name
    return found
