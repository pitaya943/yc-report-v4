"""Pages: the templates, the shared layout, and who is signed in."""

import base64
import hashlib
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, PrefixLoader, select_autoescape

from app.accounts import service as accounts
from app.core.db import request_transaction
from app.core.outcomes import Outcome, Refusal
from app.core.permissions import Actor

SESSION_COOKIE = "session"
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


def signed_in_actor(request: Request) -> Actor | None:
    """Who this request's session cookie belongs to, if anyone.

    Leaves the answer in ``request.state.actor``, where the refusal handler
    looks for the person to record on ACCESS_DENIED.
    """
    if not hasattr(request.state, "actor"):
        token = request.cookies.get(SESSION_COOKIE)
        conn = request_transaction(request).connection()
        request.state.actor = accounts.actor_of_token(conn, token) if token else None
    return request.state.actor


def current_actor(request: Request) -> Actor:
    """FastAPI dependency for every protected page and action."""
    actor = signed_in_actor(request)
    if actor is None:
        raise Refusal(Outcome.UNAUTHENTICATED, "請重新登入")
    return actor


def render(request: Request, template: str, *, status: int = 200, **context: object) -> HTMLResponse:
    page = _templates.get_template(template).render(
        actor=getattr(request.state, "actor", None), role_labels=ROLE_LABELS, htmx=_HTMX, **context
    )
    return HTMLResponse(page, status_code=status)


def sign_in_page(request: Request, *, status: int = 200, message: str | None = None) -> HTMLResponse:
    return render(request, "accounts/sign_in.html", status=status, groups=accounts.GROUP_LABELS, message=message)


def refusal_page(request: Request, refusal: Refusal) -> HTMLResponse:
    """What a person sees when refused. Not being signed in shows the sign-in page itself."""
    status = refusal.outcome.status
    if refusal.outcome is Outcome.UNAUTHENTICATED:
        return sign_in_page(request, status=status, message=refusal.message)
    return render(request, "core/error.html", status=status, message=refusal.message)
