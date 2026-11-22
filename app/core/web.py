"""Pages: the templates, the shared layout, and who is signed in."""

import base64
import hashlib
import secrets
from pathlib import Path

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, PrefixLoader, select_autoescape

from app.accounts import service as accounts
from app.accounts.store import Session
from app.core.outcomes import Outcome, Refusal
from app.core.permissions import Actor

SESSION_COOKIE = "session"
CSRF_HEADER = "X-CSRF-Token"
CSRF_FIELD = "csrf_token"
_SAFE_METHODS = ("GET", "HEAD")
_FORM_CONTENT_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")
# Signing in starts a session; it is not an action of the one the browser may
# still hold (a sign-in page left open in another tab has no token to send).
_NO_TOKEN_NEEDED = frozenset({("POST", "/sign-in")})
ROLE_LABELS = {"OWNER": "擁有者", "ADMIN": "管理員", "USER": "員工"}

_APP = Path(__file__).resolve().parents[1]
STATIC_DIR = _APP / "core" / "static"
_HTMX_FILE = "htmx-2.0.4.min.js"
_HTMX = {
    "url": f"/static/{_HTMX_FILE}",
    # Worked out from the file that is served, so the two cannot disagree.
    "integrity": "sha384-"
    + base64.b64encode(hashlib.sha384((STATIC_DIR / _HTMX_FILE).read_bytes()).digest()).decode(),
}

# Each package's templates are reached as "<package>/<file>", e.g. "accounts/sign_in.html".
_templates = Environment(
    loader=PrefixLoader(
        {directory.parent.name: FileSystemLoader(directory) for directory in sorted(_APP.glob("*/templates"))}
    ),
    autoescape=select_autoescape(default=True, default_for_string=True),
)


def session_of(request: Request) -> Session | None:
    """The session this request's cookie belongs to, if it is still good. The one place a session is resolved.

    Resolving it is using it: the idle window restarts, or the session ends
    because it was idle too long. That is committed on its own, whatever
    becomes of the request, so a refused request still counts as use and a
    timed-out session stays ended.

    Leaves the person in ``request.state.actor``, where the refusal handler
    looks for whom to record on ACCESS_DENIED.
    """
    if not hasattr(request.state, "session"):
        token = request.cookies.get(SESSION_COOKIE)
        session = None
        if token:
            with request.app.state.database.transaction() as conn:
                session = accounts.use_session(conn, request.app.state.clock, token)
        request.state.session = session
        request.state.actor = session.actor if session else None
    return request.state.session


def signed_in_actor(request: Request) -> Actor | None:
    session = session_of(request)
    return session.actor if session else None


async def _csrf_form_field(request: Request) -> str | None:
    """The anti-forgery token of a plain form, for requests that do not carry it in the header."""
    if request.method in _SAFE_METHODS or CSRF_HEADER in request.headers:
        return None
    if request.headers.get("content-type", "").startswith(_FORM_CONTENT_TYPES):
        value = (await request.form()).get(CSRF_FIELD)
        return value if isinstance(value, str) else None
    return None


def guard_session(request: Request, form_token: str | None = Depends(_csrf_form_field)) -> None:
    """Runs before every route (app/main.py): resolves the session and checks the anti-forgery token.

    The session is resolved here, before the route takes the request's
    connection, so no request holds one connection while waiting for another.

    A request that changes something and carries a session must carry that
    session's anti-forgery token, in the header or in the form.
    """
    session = session_of(request)
    if session is None or request.method in _SAFE_METHODS:
        return
    if (request.method, request.url.path) in _NO_TOKEN_NEEDED:
        return
    token = request.headers.get(CSRF_HEADER) or form_token or ""
    if not secrets.compare_digest(token.encode(), session.csrf_token.encode()):
        raise Refusal(Outcome.FORBIDDEN, "請求未通過驗證", attempted=f"{request.method} {request.url.path}")


def current_actor(request: Request) -> Actor:
    """FastAPI dependency for every protected page and action."""
    actor = signed_in_actor(request)
    if actor is None:
        raise Refusal(Outcome.UNAUTHENTICATED, "請重新登入")
    return actor


def render(request: Request, template: str, *, status: int = 200, **context: object) -> HTMLResponse:
    page = _templates.get_template(template).render(
        session=getattr(request.state, "session", None),
        role_labels=ROLE_LABELS,
        htmx=_HTMX,
        csrf={"header": CSRF_HEADER, "field": CSRF_FIELD},
        status=status,
        **context,
    )
    return HTMLResponse(page, status_code=status)


def sign_in_page(
    request: Request, *, status: int = 200, message: str | None = None, notice: str | None = None
) -> HTMLResponse:
    """``message`` is a refusal; ``notice`` is something that went well."""
    return render(
        request, "accounts/sign_in.html", status=status, groups=accounts.GROUPS, message=message, notice=notice
    )


def refusal_page(request: Request, refusal: Refusal) -> HTMLResponse:
    """What a person sees when refused. Not being signed in shows the sign-in page itself."""
    status = refusal.outcome.status
    if refusal.outcome is Outcome.UNAUTHENTICATED:
        return sign_in_page(request, status=status, message=refusal.message)
    return render(request, "core/error.html", status=status, message=refusal.message)
