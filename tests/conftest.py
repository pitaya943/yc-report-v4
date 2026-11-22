import os
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings, load_settings
from app.core.migrate import migrate
from app.main import create_app
from tests.support import pg
from tests.support.clock import TestClock


@pytest.fixture(scope="session")
def pg_server() -> Iterator[str]:
    """A PostgreSQL server where the tests may create databases."""
    with pg.test_server(os.environ) as url:
        yield url


@pytest.fixture(scope="session")
def template_database(pg_server: str) -> Iterator[str]:
    """A migrated database that every test database is copied from."""
    name = pg.create_database(pg_server)
    migrate(pg.url_for(pg_server, name), TestClock())
    yield name
    pg.drop_database(pg_server, name)


@pytest.fixture
def make_database(pg_server: str, template_database: str) -> Iterator[Callable[[], str]]:
    """Call it for the URL of a new migrated database; all are dropped after the test."""
    with pg.databases(pg_server, template_database) as make:
        yield make


@pytest.fixture
def empty_database(pg_server: str) -> Iterator[str]:
    """The URL of a database with nothing in it, not even the migrations table."""
    with pg.databases(pg_server, None) as make:
        yield make()


@pytest.fixture
def database_url(make_database: Callable[[], str]) -> str:
    """This test's own migrated database."""
    return make_database()


@pytest.fixture
def clock() -> TestClock:
    return TestClock()


@pytest.fixture
def settings(database_url: str) -> Settings:
    return load_settings(
        {"DATABASE_URL": database_url, "APP_ENV": "test", "PASSWORD_HASH_PROFILE": "fast"}
    )


@pytest.fixture
def app(settings: Settings, clock: TestClock) -> FastAPI:
    return create_app(settings, clock)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # raise_server_exceptions=False: an unhandled error is a 500 response, as
    # it is for a real client.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
