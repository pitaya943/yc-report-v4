"""Commands: python -m app check-config | migrate | serve"""

import argparse
import os
import sys

import psycopg
import uvicorn

from app.core import migrate as migrations
from app.core.clock import SystemClock
from app.core.config import ConfigError, Settings, load_settings
from app.main import create_app


class CommandFailed(Exception):
    """A command could not do its work; the message is what the operator reads."""


def _check_config(settings: Settings, clock: SystemClock, args: argparse.Namespace) -> None:
    print("\n".join(settings.describe()))


def _migrate(settings: Settings, clock: SystemClock, args: argparse.Namespace) -> None:
    try:
        applied = migrations.migrate(settings.database_url, clock)
    except (migrations.MigrationError, psycopg.Error) as error:
        raise CommandFailed(f"migration 失敗：{error}") from error
    print("已套用：" + "、".join(applied) if applied else "沒有待套用的 migration")


def _serve(settings: Settings, clock: SystemClock, args: argparse.Namespace) -> None:
    _migrate(settings, clock, args)
    # proxy_headers off: the client address is worked out in one place, from
    # TRUSTED_PROXY_HOPS, not by the server's own rules.
    uvicorn.run(create_app(settings, clock), host=args.host, port=args.port, proxy_headers=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-config", help="讀設定並印出每一項的狀態").set_defaults(run=_check_config)
    commands.add_parser("migrate", help="套用尚未套用的 migration").set_defaults(run=_migrate)
    serve = commands.add_parser("serve", help="migrate 之後啟動伺服器")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(run=_serve)
    args = parser.parse_args(argv)

    try:
        settings = load_settings(os.environ)
    except ConfigError as error:
        print(error, file=sys.stderr)
        return 2

    try:
        args.run(settings, SystemClock(settings.clock_offset_minutes), args)
    except CommandFailed as error:
        print(error, file=sys.stderr)
        return 1
    except psycopg.Error as error:
        print(f"資料庫錯誤：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
