import re

import pytest

from app.core.outcomes import Outcome, Refusal
from tests.support import recorder
from tests.support.cli import REPO
from tests.support.html import alert_texts

# From the table in docs/spec/conventions.md.
STATUS = {
    "UNAUTHENTICATED": 401,
    "FORBIDDEN": 403,
    "INVALID": 422,
    "CONFLICT": 409,
    "LOCKED": 423,
    "RATE_LIMITED": 429,
    "BLOCKED": 409,
}
MESSAGE = "密碼錯誤，請重試 <b>&\"引號\"</b>"


@pytest.fixture(autouse=True)
def routes(app):
    @app.get("/_test/refuse/{name}")
    def refuse(name: str):
        raise Refusal(Outcome[name], MESSAGE)


def test_the_outcomes_are_those_of_the_spec_conventions():
    table = (REPO / "docs/spec/conventions.md").read_text(encoding="utf-8")
    documented = {name: int(status) for name, status in re.findall(r"^\| `([A-Z_]+)` \|[^|]*\| (\d{3}) \|", table, re.M)}

    assert documented == STATUS
    assert {outcome.name: outcome.status for outcome in Outcome} == documented


@pytest.mark.parametrize("name", STATUS)
def test_a_refusal_is_json_when_the_request_accepts_json(client, name):
    response = client.get(f"/_test/refuse/{name}", headers={"Accept": "application/json"})

    assert response.status_code == STATUS[name]
    assert response.headers["X-Outcome"] == name
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"outcome": name, "message": MESSAGE}


@pytest.mark.parametrize("name", STATUS)
@pytest.mark.parametrize("accept", ["text/html,application/xhtml+xml,*/*;q=0.8", None])
def test_a_refusal_is_otherwise_a_page_with_the_message_in_an_alert(client, name, accept):
    response = client.get(f"/_test/refuse/{name}", headers={"Accept": accept} if accept else {})

    assert response.status_code == STATUS[name]
    assert response.headers["X-Outcome"] == name
    assert response.headers["content-type"].startswith("text/html")
    assert alert_texts(response.text) == [MESSAGE]


def test_an_unknown_path_is_404_and_writes_nothing(client, database_url):
    before = recorder.snapshot(database_url)

    response = client.get("/no-such-page")

    assert response.status_code == 404
    assert "X-Outcome" not in response.headers
    assert recorder.diff(before, recorder.snapshot(database_url)) == []
