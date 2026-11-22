"""The real server, started as a person would start it, for tests that drive it from outside."""

import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

import httpx2

from tests.support.cli import REPO, app_environ


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def running_app(database_url: str, *, port: int | None = None, **settings: str) -> Iterator[str]:
    """Run ``python -m app serve`` and yield its address once it answers; stop it and wait for it afterwards.

    Fails when the process ends before answering (a taken port, a bad
    setting), so what answers at the address is the process started here.
    """
    port = port or _free_port()
    url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "-m", "app", "serve", "--port", str(port)],
        cwd=REPO,
        env=app_environ(DATABASE_URL=database_url, **settings),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 60
        while True:
            if server.poll() is not None:
                raise RuntimeError(f"the server ended with status {server.returncode}:\n{server.stderr.read()}")
            try:
                if httpx2.get(f"{url}/health", timeout=5).status_code == 200:
                    break
            except httpx2.TransportError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError(f"the server did not answer at {url}/health within 60 seconds")
            time.sleep(0.1)
        if server.poll() is not None:
            raise RuntimeError(f"something else answers at {url}; the server ended:\n{server.stderr.read()}")
        yield url
    finally:
        server.terminate()
        try:
            server.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            server.communicate()
