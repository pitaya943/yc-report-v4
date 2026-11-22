"""create-owner and seed-demo (design section 10)."""

import getpass
import os
import pty
import select
import subprocess
import sys
import time

import psycopg
import pytest

from app.__main__ import main
from app.accounts import demo
from tests.support import spec
from tests.support.cli import REPO, app_environ, run_app

OWNER_PASSWORD = "only-typed-擁有者"


@pytest.fixture
def typed(monkeypatch, database_url):
    """Run a command in this process, answering its prompts: the name on the visible prompt, passwords on the hidden one."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PASSWORD_HASH_PROFILE", "fast")

    def run(command: str, *, name: str = "", passwords: tuple[str, ...] = ()) -> int:
        hidden = iter(passwords)
        monkeypatch.setattr("builtins.input", lambda prompt="": name)
        monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(hidden))
        return main([command])

    return run


def accounts_in(database_url: str) -> list[tuple]:
    with psycopg.connect(database_url) as conn:
        return conn.execute(
            "select display_name, role, zone, big_meter, archived_at is not null from accounts order by id"
        ).fetchall()


def test_create_owner_creates_the_owner_who_can_then_sign_in(typed, client, database_url, capsys):
    status = typed("create-owner", name="Boss", passwords=(OWNER_PASSWORD, OWNER_PASSWORD))

    assert status == 0
    assert accounts_in(database_url) == [("Boss", "OWNER", "WEST", False, False)]
    response = client.post(
        "/sign-in", data={"group": "admin", "name": "Boss", "password": OWNER_PASSWORD}, follow_redirects=False
    )
    assert (response.status_code, response.headers["location"]) == (303, "/review")
    assert "Boss" in client.get("/review").text


def test_create_owner_is_refused_when_there_is_an_owner(typed, database_url, capsys):
    typed("create-owner", name="Boss", passwords=(OWNER_PASSWORD, OWNER_PASSWORD))

    status = typed("create-owner", name="Second", passwords=(OWNER_PASSWORD, OWNER_PASSWORD))

    assert status != 0
    assert "擁有者只能有一位" in capsys.readouterr().err
    assert [name for name, *_ in accounts_in(database_url)] == ["Boss"]


@pytest.mark.parametrize(
    ("name", "passwords", "message"),
    [
        ("Boss", (OWNER_PASSWORD, OWNER_PASSWORD + "x"), "兩次輸入的密碼不一致"),
        ("Boss", ("12345", "12345"), "密碼長度須為 6 至 30 個字"),
        ("Boss", ("x" * 31, "x" * 31), "密碼長度須為 6 至 30 個字"),
        ("", (OWNER_PASSWORD, OWNER_PASSWORD), "請輸入顯示名稱"),
    ],
)
def test_create_owner_refuses_what_was_typed_wrongly(typed, database_url, capsys, name, passwords, message):
    status = typed("create-owner", name=name, passwords=passwords)

    assert status != 0
    assert message in capsys.readouterr().err
    assert accounts_in(database_url) == []


def test_the_owner_password_is_in_no_output_and_no_audit_row(typed, database_url, capsys):
    typed("create-owner", name="Boss", passwords=(OWNER_PASSWORD, OWNER_PASSWORD))

    output = capsys.readouterr()
    assert OWNER_PASSWORD not in output.out + output.err
    with psycopg.connect(database_url) as conn:
        rows = conn.execute("select actor_name, type, description from audit_log").fetchall()
        stored = conn.execute("select row_to_json(a)::text from accounts a").fetchall()
    assert rows == [("SYSTEM", "ACCOUNT_CREATE", "以指令建立擁有者：Boss")]
    assert OWNER_PASSWORD not in str(stored)


def test_create_owner_does_not_take_the_password_as_an_argument(database_url):
    for extra in (["--password", OWNER_PASSWORD], [OWNER_PASSWORD]):
        result = run_app("create-owner", *extra, DATABASE_URL=database_url, APP_ENV="test")

        assert result.returncode != 0
        assert "unrecognized arguments" in result.stderr
    assert accounts_in(database_url) == []


def test_create_owner_reads_the_password_from_a_terminal_without_showing_it(database_url):
    """On a real terminal: what is typed at the name prompt is shown, what is typed at the password prompts is not."""
    master, slave = pty.openpty()
    process = subprocess.Popen(
        [sys.executable, "-m", "app", "create-owner"],
        cwd=REPO,
        env=app_environ(DATABASE_URL=database_url, APP_ENV="test", PASSWORD_HASH_PROFILE="fast"),
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
    )
    os.close(slave)
    shown = ""

    def read_until(text: str | None) -> None:
        """Read what the terminal shows until ``text`` appears, or (None) until the command has ended."""
        nonlocal shown
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and (text is None or text not in shown):
            if select.select([master], [], [], 0.2)[0]:
                try:
                    chunk = os.read(master, 4096)
                except OSError:  # the command closed the terminal
                    return
                shown += chunk.decode("utf-8", "replace")
            elif text is None and process.poll() is not None:
                return

    try:
        read_until("顯示名稱：")
        os.write(master, b"Boss\n")
        read_until("密碼（輸入時不顯示）：")
        os.write(master, OWNER_PASSWORD.encode() + b"\n")
        read_until("再輸入一次密碼：")
        os.write(master, OWNER_PASSWORD.encode() + b"\n")
        read_until(None)
        assert process.wait(timeout=60) == 0, shown
    finally:
        process.kill()
        os.close(master)

    assert "Boss" in shown.split("密碼（輸入時不顯示）：")[0], "the terminal shows what is typed at a visible prompt"
    assert OWNER_PASSWORD not in shown
    assert "已建立擁有者：Boss" in shown
    assert [name for name, *_ in accounts_in(database_url)] == ["Boss"]


def test_seed_demo_loads_the_accounts_of_the_shared_background(typed, client, database_url, capsys):
    [table] = [step.table for step in spec.background() if step.text == "these accounts exist:"]
    header, *rows = table
    background = [
        (row["name"], row["role"], row["zone"], row["big_meter"] == "yes", row["archived"] == "yes")
        for row in (dict(zip(header, values)) for values in rows)
    ]

    status = typed("seed-demo")

    assert status == 0
    assert len(background) == 9
    assert accounts_in(database_url) == background
    assert demo.PASSWORD in capsys.readouterr().out
    response = client.post(
        "/sign-in", data={"group": "south", "name": "Nan", "password": demo.PASSWORD}, follow_redirects=False
    )
    assert (response.status_code, response.headers["location"]) == (303, "/reports")


def test_seed_demo_is_refused_when_there_are_accounts(typed, database_url, capsys):
    typed("create-owner", name="Boss", passwords=(OWNER_PASSWORD, OWNER_PASSWORD))

    status = typed("seed-demo")

    assert status != 0
    assert "示範帳戶只能載入到空的系統" in capsys.readouterr().err
    assert [name for name, *_ in accounts_in(database_url)] == ["Boss"]


def test_seed_demo_is_refused_in_production(database_url):
    result = run_app("seed-demo", DATABASE_URL=database_url, APP_ENV="production")

    assert result.returncode != 0
    assert "APP_ENV=production 不可載入示範帳戶" in result.stderr
    assert accounts_in(database_url) == []
