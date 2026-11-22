import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def app_environ(**settings: str) -> dict[str, str]:
    """An environment holding only what a process needs to start, plus ``settings``."""
    return {"PATH": os.environ.get("PATH", ""), **settings}


def run_app(*args: str, timeout: float = 60, **settings: str) -> subprocess.CompletedProcess[str]:
    """Run ``python -m app <args>`` with exactly ``settings`` as its configuration."""
    return subprocess.run(
        [sys.executable, "-m", "app", *args],
        cwd=REPO,
        env=app_environ(**settings),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
