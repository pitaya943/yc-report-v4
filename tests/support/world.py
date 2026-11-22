"""What one spec scenario works with: the people, their sessions, the request sent, what it wrote.

The common steps (tests/steps/common) are thin wrappers over this class, and
the steps of each area send their requests through it.
"""

import re
from datetime import datetime

import psycopg
from fastapi.testclient import TestClient
from httpx2 import Response

from app.accounts import service as accounts
from app.core.clock import TAIPEI
from tests.support import recorder
from tests.support.cli import REPO
from tests.support.clock import TestClock
from tests.support.html import elements
from tests.support.recorder import Change
from tests.support.spec import SpecStep

# Every account of the shared background has this password.
PASSWORD = "background-password-正確"
SESSION_COOKIE = "session"
CSRF_HEADER = "X-CSRF-Token"
CSRF_FIELD = "csrf_token"
SYSTEM = "SYSTEM"


def outcome_statuses() -> dict[str, int]:
    """The HTTP status of each outcome class, from the table in docs/spec/conventions.md."""
    table = (REPO / "docs/spec/conventions.md").read_text(encoding="utf-8")
    return {name: int(status) for name, status in re.findall(r"^\| `([A-Z_]+)` \|[^|]*\| (\d{3}) \|", table, re.M)}


def parse_moment(text: str) -> datetime:
    """``2026-11-15 10:00`` or ``2026-11-15 10:00:30``, in Asia/Taipei."""
    layout = "%Y-%m-%d %H:%M:%S" if text.count(":") == 2 else "%Y-%m-%d %H:%M"
    return datetime.strptime(text, layout).replace(tzinfo=TAIPEI)


def sign_in_group(account: dict[str, str]) -> str:
    """The group of the sign-in page that lists this account (appendix B, 登入群組)."""
    return "admin" if account["role"] in ("OWNER", "ADMIN") else account["zone"].lower()


class World:
    def __init__(self, client: TestClient, clock: TestClock, database_url: str):
        self.client = client
        self.clock = clock
        self.database_url = database_url
        self.accounts: dict[str, dict[str, str]] = {}
        self.sessions: dict[str, str] = {}
        self._csrf_tokens: dict[str, str] = {}
        self.responses: list[Response] = []
        self._before: recorder.Snapshot | None = None
        self._accounted: list[Change] = []

    # Setting the scene

    def load_background(self, steps: list[SpecStep]) -> None:
        """Apply the shared background of docs/spec/background.md."""
        for step in steps:
            if match := re.fullmatch(r'the clock is "(.+)" in Asia/Taipei', step.text):
                self.clock.set(parse_moment(match.group(1)))
            elif step.text == "these accounts exist:":
                header, *rows = step.table
                self.create_accounts([dict(zip(header, row)) for row in rows])
            elif step.text == "unit prices, retention rates, and the retention cap are the defaults in Appendix A":
                pass  # Nothing stores them yet; the task that builds settings loads them here.
            else:
                raise AssertionError(f"the shared background has a step that nothing loads: {step.text}")

    def create_accounts(self, rows: list[dict[str, str]]) -> None:
        passwords = self.client.app.state.passwords
        with psycopg.connect(self.database_url) as conn:
            for row in rows:
                account_id = accounts.create_account(
                    conn,
                    passwords,
                    name=row["name"],
                    role=row["role"],
                    zone=row["zone"],
                    big_meter=row["big_meter"] == "yes",
                    password=PASSWORD,
                )
                if row["archived"] == "yes":
                    # No action archives an account yet; the task that builds it replaces this.
                    conn.execute("update accounts set archived_at = %s where id = %s", (self.clock.now(), account_id))
                self.accounts[row["name"]] = {**row, "id": account_id}

    def sign_in(self, name: str) -> None:
        """Give ``name`` a session, the way the sign-in page would."""
        form = {"group": sign_in_group(self.accounts[name]), "name": name, "password": PASSWORD}
        response = self._request("POST", "/sign-in", data=form)
        assert response.status_code == 303, f"{name} could not sign in: {response.status_code} {response.text}"
        self.signed_in(name, response)

    def signed_in(self, name: str, response: Response) -> None:
        """Take over the session a successful sign-in response started, and read its page for the anti-forgery token."""
        self.sessions[name] = response.cookies[SESSION_COOKIE]
        page = self.open_page(response.headers["location"], actor=name)
        assert page.status_code == 200, f"{name} has no landing page: {page.status_code} {page.text}"
        [self._csrf_tokens[self.sessions[name]]] = {
            attrs["value"] for attrs, _ in elements(page.text, "input") if attrs.get("name") == CSRF_FIELD
        }

    def csrf_token(self, name: str) -> str:
        """The anti-forgery token the pages of ``name``'s session carry."""
        return self._csrf_tokens[self.sessions[name]]

    # The action

    def send(self, method: str, path: str, *, actor: str | None = None, csrf: bool = True, **kwargs) -> Response:
        """Send the scenario's request, as ``actor`` if given, otherwise as a visitor.

        Refusals come back as JSON. What the database held before the first
        request sent this way is what "written" is measured against.

        A request of ``actor`` that changes something carries the session's
        anti-forgery token in the header, as the shared layout makes every
        page do; ``csrf=False`` leaves it out.
        """
        if self._before is None:
            self._before = recorder.snapshot(self.database_url)
        cookie = self.sessions[actor] if actor else None
        if csrf and cookie in self._csrf_tokens and method.upper() not in ("GET", "HEAD"):
            kwargs["headers"] = {CSRF_HEADER: self._csrf_tokens[cookie], **(kwargs.get("headers") or {})}
        response = self._request(method, path, session=cookie, **kwargs)
        self.responses.append(response)
        return response

    def open_page(self, path: str, *, actor: str | None = None) -> Response:
        """Look at a page the way a browser would, to check what the scenario's request led to."""
        cookie = self.sessions[actor] if actor else None
        return self._request("GET", path, session=cookie, headers={"Accept": "text/html"})

    def _request(self, method: str, path: str, *, session: str | None = None, headers=None, **kwargs) -> Response:
        headers = {"Accept": "application/json", **(headers or {})}
        if session:
            headers["Cookie"] = f"{SESSION_COOKIE}={session}"
        try:
            return self.client.request(method, path, headers=headers, follow_redirects=False, **kwargs)
        finally:
            # Only the session named by the caller travels; nothing is remembered between requests.
            self.client.cookies.clear()

    # What happened

    def assert_rejected(self, outcome: str, message: str | None = None) -> None:
        assert self.responses, "no request was sent"
        status = outcome_statuses()[outcome]
        for response in self.responses:
            where = f"{response.request.method} {response.request.url.path}"
            assert response.status_code == status, f"{where}: status {response.status_code}, expected {status}"
            assert response.headers.get("X-Outcome") == outcome, f"{where}: X-Outcome {response.headers.get('X-Outcome')}"
            body = response.json()
            assert body["outcome"] == outcome, where
            if message is not None:
                assert body["message"] == message, where

    def assert_accepted(self) -> None:
        assert self.responses, "no request was sent"
        for response in self.responses:
            where = f"{response.request.method} {response.request.url.path}"
            assert response.status_code < 400, f"{where}: status {response.status_code} {response.text}"
            assert "X-Outcome" not in response.headers, where

    def changes(self) -> list[Change]:
        """Everything the scenario's request changed in the database."""
        assert self._before is not None, "no request was sent"
        return recorder.diff(self._before, recorder.snapshot(self.database_url))

    def assert_nothing_written(self) -> None:
        assert self.changes() == []

    def assert_no_audit_row_written(self) -> None:
        assert self._audit_rows() == []

    def assert_audit_rows_written(self, type: str, *, actor: str | None = None, count: int = 1) -> None:
        """Exactly ``count`` audit rows of this type were added; with ``actor``, all of them by that actor.

        The rows are then accounted for: "nothing else is written" does not count them.
        """
        rows = [change for change in self._audit_rows() if change.after["type"] == type]
        assert len(rows) == count, f"{len(rows)} audit rows of type {type} were written, expected {count}"
        if actor is not None:
            account_id = None if actor == SYSTEM else self.accounts[actor]["id"]
            for row in rows:
                assert (row.after["actor_name"], row.after["actor_account_id"]) == (actor, account_id)
        self._accounted += rows

    def assert_nothing_else_written(self) -> None:
        assert [change for change in self.changes() if change not in self._accounted] == []

    def _audit_rows(self) -> list[Change]:
        return [change for change in self.changes() if change.table == "audit_log" and change.kind == "added"]
