import psycopg
import pytest
from fastapi import Depends, HTTPException

from app.core.db import connection
from app.core.outcomes import Outcome, Refusal


@pytest.fixture(autouse=True)
def routes(app, database_url):
    with psycopg.connect(database_url) as conn:
        conn.execute("create table note (body text)")

    def write(conn):
        conn.execute("insert into note values ('first')")
        conn.execute("insert into note values ('second')")

    @app.post("/_test/succeed")
    def succeed(conn=Depends(connection)):
        write(conn)
        return {"ok": True}

    @app.post("/_test/crash")
    def crash(conn=Depends(connection)):
        write(conn)
        raise RuntimeError("boom")

    @app.post("/_test/refuse")
    def refuse(conn=Depends(connection)):
        write(conn)
        raise Refusal(Outcome.CONFLICT, "不行")

    @app.post("/_test/http-error")
    def http_error(conn=Depends(connection)):
        write(conn)
        raise HTTPException(status_code=400)


def notes(database_url: str) -> list[str]:
    with psycopg.connect(database_url) as conn:
        return [body for (body,) in conn.execute("select body from note order by body")]


def test_a_request_that_succeeds_commits(client, database_url):
    assert client.post("/_test/succeed").status_code == 200
    assert notes(database_url) == ["first", "second"]


@pytest.mark.parametrize(
    ("path", "status"),
    [("/_test/crash", 500), ("/_test/refuse", 409), ("/_test/http-error", 400)],
)
def test_a_request_that_raises_rolls_back_everything_it_wrote(client, database_url, path, status):
    assert client.post(path).status_code == status
    assert notes(database_url) == []


def test_connections_go_back_to_the_pool_whatever_the_result(client, database_url):
    # More requests than the pool has connections; a leak would block here.
    expected = {"/_test/crash": 500, "/_test/refuse": 409, "/_test/http-error": 400, "/_test/succeed": 200}
    for _ in range(8):
        for path, status in expected.items():
            assert client.post(path).status_code == status
    assert len(notes(database_url)) == 16
