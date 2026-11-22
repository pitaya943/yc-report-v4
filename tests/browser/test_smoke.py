"""A real browser against a really started server (design 11.4)."""

import os

import pytest

from app.accounts import demo
from tests.support import browser
from tests.support.cli import run_app
from tests.support.server import running_app


@pytest.mark.parametrize(("group", "name"), [("west", "Wen"), ("admin", "Admin1")])
def test_a_person_signs_in_sees_their_landing_page_and_signs_out(database_url, group, name):
    reason = browser.missing()
    if reason:
        if os.environ.get("REQUIRE_BROWSER") == "1":
            pytest.fail(f"REQUIRE_BROWSER=1 但瀏覽器測試無法執行：{reason}")
        pytest.skip(f"瀏覽器測試略過：{reason}")
    seeded = run_app("seed-demo", DATABASE_URL=database_url, PASSWORD_HASH_PROFILE="fast")
    assert seeded.returncode == 0, seeded.stderr

    with running_app(database_url, PASSWORD_HASH_PROFILE="fast") as url:
        result = browser.sign_in_and_out(url, group=group, name=name, password=demo.PASSWORD)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok: landing-page-asks-to-sign-in-again" in result.stdout
