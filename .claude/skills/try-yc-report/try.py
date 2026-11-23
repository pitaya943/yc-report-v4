#!/usr/bin/env python3
"""Start the real app on a database of its own, load the demo accounts, and sign in and out in a browser.

Run from the repository root, with the project installed (pip install -e ".[dev]"):

    python .claude/skills/try-yc-report/try.py --evidence docs/tasks/<slug>/evidence/sign-in

Exits non-zero when any step does not give the expected result. With --keep
the server stays up afterwards, at the address printed, until Ctrl-C.
"""

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from app.accounts import demo  # noqa: E402
from tests.support import browser, pg  # noqa: E402
from tests.support.cli import run_app  # noqa: E402
from tests.support.server import running_app  # noqa: E402

SETTINGS = {"APP_ENV": "development", "PASSWORD_HASH_PROFILE": "fast"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--group", default="west", help="admin, west or south (default: west)")
    parser.add_argument("--name", default="Wen", help="a demo account of that group (default: Wen)")
    parser.add_argument("--evidence", type=Path, help="directory for the screenshots and the transcript")
    parser.add_argument("--port", type=int, help="port to serve on (default: a free one); fails if it is taken")
    parser.add_argument("--keep", action="store_true", help="leave the server running until Ctrl-C")
    args = parser.parse_args()

    reason = browser.missing()
    if reason:
        print(f"cannot drive a browser here: {reason}", file=sys.stderr)
        return 2

    # TEST_DATABASE_URL if set, otherwise a throwaway PostgreSQL of our own.
    with pg.test_server(os.environ) as server, pg.databases(server, None) as make_database:
        database_url = make_database()
        for command in ("migrate", "seed-demo"):
            done = run_app(command, DATABASE_URL=database_url, **SETTINGS)
            print(f"$ python -m app {command}\n{done.stdout}{done.stderr}", end="")
            if done.returncode != 0:
                return 1

        with running_app(database_url, port=args.port, **SETTINGS) as url:
            print(f"the app answers at {url}")
            result = browser.sign_in_and_out(
                url, group=args.group, name=args.name, password=demo.PASSWORD, screenshots=args.evidence
            )
            transcript = result.stdout + result.stderr
            print(transcript, end="")
            if args.evidence:
                (args.evidence / "transcript.txt").write_text(
                    f"{args.name} ({args.group}) at {url}\n{transcript}exit status {result.returncode}\n",
                    encoding="utf-8",
                )
            if result.returncode == 0 and args.keep:
                print(f"still serving at {url}; demo password: {demo.PASSWORD}; Ctrl-C to stop")
                try:
                    while True:
                        input()
                except (KeyboardInterrupt, EOFError):
                    pass
        print("the server has stopped")
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
