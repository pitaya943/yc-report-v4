"""Refusals: the one way to say no, and the one place that turns it into a response."""

from enum import Enum
from html import escape

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from app.core import audit
from app.core.db import request_transaction


class Outcome(Enum):
    """Names and HTTP statuses come from docs/spec/conventions.md.

    The status is not the enum value: CONFLICT and BLOCKED share 409, and two
    members with the same value would be one member.
    """

    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    INVALID = "INVALID"
    CONFLICT = "CONFLICT"
    LOCKED = "LOCKED"
    RATE_LIMITED = "RATE_LIMITED"
    BLOCKED = "BLOCKED"

    @property
    def status(self) -> int:
        return _STATUS[self]


_STATUS = {
    Outcome.UNAUTHENTICATED: 401,
    Outcome.FORBIDDEN: 403,
    Outcome.INVALID: 422,
    Outcome.CONFLICT: 409,
    Outcome.LOCKED: 423,
    Outcome.RATE_LIMITED: 429,
    Outcome.BLOCKED: 409,
}


class Refusal(Exception):
    def __init__(self, outcome: Outcome, message: str, *, attempted: str | None = None):
        super().__init__(message)
        self.outcome = outcome
        self.message = message
        # The action that was refused; goes into the ACCESS_DENIED description.
        self.attempted = attempted


def _handle_refusal(request: Request, refusal: Refusal) -> Response:
    # Roll back now, not when the response leaves: the connection goes back to
    # the pool before the audit row asks for one.
    request_transaction(request).finish(commit=False)

    # Whoever resolves the signed-in person puts the Actor in request.state.actor.
    actor = getattr(request.state, "actor", None)
    if refusal.outcome is Outcome.FORBIDDEN and actor is not None:
        attempted = refusal.attempted or f"{request.method} {request.url.path}"
        with request.app.state.database.transaction() as conn:
            audit.write(
                conn,
                request.app.state.clock,
                actor,
                audit.AuditType.ACCESS_DENIED,
                f"{refusal.message}：{attempted}",
            )

    headers = {"X-Outcome": refusal.outcome.name}
    status = refusal.outcome.status
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse(
            {"outcome": refusal.outcome.name, "message": refusal.message},
            status_code=status,
            headers=headers,
        )
    page = (
        '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        f"<title>{status}</title></head>"
        f'<body><main><p role="alert">{escape(refusal.message)}</p></main></body></html>'
    )
    return HTMLResponse(page, status_code=status, headers=headers)


def install(app: FastAPI) -> None:
    # A plain def: Starlette runs it in the thread pool, so its database work
    # does not block the event loop.
    app.add_exception_handler(Refusal, _handle_refusal)
