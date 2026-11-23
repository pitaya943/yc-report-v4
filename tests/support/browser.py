"""Running the browser script (tests/browser/smoke.cjs) with Node's Playwright."""

import os
import shutil
import subprocess
from pathlib import Path

from tests.support.cli import REPO

SCRIPT = REPO / "tests" / "browser" / "smoke.cjs"
# Where this project's working environment keeps them; NODE_PATH and
# PLAYWRIGHT_BROWSERS_PATH say where they are anywhere else.
_NODE_MODULES = Path("/opt/node-tools/node_modules")
_BROWSERS = Path("/opt/pw-browsers")


def _environ() -> dict[str, str]:
    environ = dict(os.environ)
    if _NODE_MODULES.is_dir():
        environ["NODE_PATH"] = os.pathsep.join(filter(None, [environ.get("NODE_PATH"), str(_NODE_MODULES)]))
    if _BROWSERS.is_dir():
        environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(_BROWSERS))
    return environ


def missing() -> str | None:
    """Why the browser script cannot run here, or None when it can."""
    node = shutil.which("node")
    if node is None:
        return "找不到 node"
    found = subprocess.run([node, "-e", "require.resolve('playwright')"], env=_environ(), capture_output=True)
    if found.returncode != 0:
        return "找不到 Node 的 playwright 套件（以 NODE_PATH 指出它的 node_modules）"
    return None


def sign_in_and_out(
    base_url: str, *, group: str, name: str, password: str, screenshots: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Drive a browser through sign-in and sign-out as ``name``; the result's return code is 0 when every step held."""
    environ = _environ() | {"BASE_URL": base_url, "GROUP": group, "NAME": name, "PASSWORD": password}
    if screenshots is not None:
        screenshots.mkdir(parents=True, exist_ok=True)
        environ["SCREENSHOT_DIR"] = str(screenshots)
    return subprocess.run(["node", str(SCRIPT)], env=environ, capture_output=True, text=True, timeout=180)
