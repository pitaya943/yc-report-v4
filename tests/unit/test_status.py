"""GET /status: what an administrator can see about the deployment."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.core.migrate import MIGRATIONS_DIR
from app.main import create_app
from tests.support.html import elements
from tests.support.world import World


def states(page: str) -> dict[str, str]:
    return {attrs["id"]: text for attrs, text in elements(page, "dd")}


@pytest.mark.parametrize("name", ["Admin1", "Kuei"])
def test_status_shows_the_four_states_to_an_administrator_and_the_owner(world: World, name):
    world.sign_in(name)

    page = world.open_page("/status", actor=name)

    newest = max(path.name[:4] for path in MIGRATIONS_DIR.glob("*.sql"))
    assert page.status_code == 200
    assert states(page.text) == {
        "database": "可連線",
        "migration-version": newest,
        "storage": "未設定",
        "bank-key": "未設定",
    }


def test_status_says_when_storage_and_the_key_are_configured_without_showing_them(world: World, database_url):
    settings = load_settings(
        {
            "DATABASE_URL": database_url,
            "APP_ENV": "test",
            "PASSWORD_HASH_PROFILE": "fast",
            "STORAGE_BACKEND": "some-bucket",
            "BANK_KEY": "a-secret-key",
        }
    )
    world.sign_in("Admin1")

    with TestClient(create_app(settings, world.clock)) as client:
        client.cookies.set("session", world.sessions["Admin1"])
        page = client.get("/status")

    assert states(page.text)["storage"] == "已設定"
    assert states(page.text)["bank-key"] == "已設定"
    assert "some-bucket" not in page.text
    assert "a-secret-key" not in page.text


def test_status_is_forbidden_for_a_user(world: World):
    world.sign_in("Wen")

    world.send("GET", "/status", actor="Wen")

    world.assert_rejected("FORBIDDEN", "禁止存取")
    world.assert_audit_rows_written("ACCESS_DENIED", actor="Wen")


def test_status_is_unauthenticated_without_a_session(world: World):
    world.send("GET", "/status")

    world.assert_rejected("UNAUTHENTICATED", "請重新登入")
    world.assert_nothing_written()
