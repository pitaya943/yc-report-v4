from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from psycopg import Connection
from starlette.datastructures import FormData

from app.accounts import service
from app.core import web
from app.core.db import connection

router = APIRouter()


async def _form(request: Request) -> FormData:
    return await request.form()


def _text(form: FormData, field: str) -> str | None:
    value = form.get(field)
    return value if isinstance(value, str) else None


def _client_address(request: Request) -> str:
    """Where the request came from, for the sign-in rate limit.

    With no trusted proxy it is the connection's peer. With n trusted proxies
    it is the n-th value from the right of X-Forwarded-For, the one the
    outermost trusted proxy wrote; anything further left came from the client
    and is never used. A request that did not pass through that many proxies
    is counted under its peer.
    """
    peer = request.client.host if request.client else "unknown"
    hops = request.app.state.settings.trusted_proxy_hops
    forwarded = [value.strip() for value in ",".join(request.headers.getlist("x-forwarded-for")).split(",")]
    if hops == 0 or len(forwarded) < hops or not forwarded[-hops]:
        return peer
    return forwarded[-hops]


@router.get("/")
def front_door(request: Request) -> Response:
    actor = web.signed_in_actor(request)
    return RedirectResponse(service.LANDING_PAGES[actor.role] if actor else "/sign-in", status_code=303)


@router.get("/sign-in")
def sign_in_page(request: Request) -> Response:
    return web.sign_in_page(request)


@router.get("/sign-in/names")
def names(request: Request, group: str | None = None, conn: Connection = Depends(connection)) -> Response:
    return web.render(request, "accounts/names.html", names=service.names_for_group(conn, group))


@router.post("/sign-in")
def sign_in(request: Request, form: FormData = Depends(_form), conn: Connection = Depends(connection)) -> Response:
    actor, token = service.sign_in(
        conn,
        request.app.state.clock,
        request.app.state.passwords,
        address=_client_address(request),
        group=_text(form, "group"),
        name=_text(form, "name"),
        password=_text(form, "password") or "",
    )
    response = RedirectResponse(service.LANDING_PAGES[actor.role], status_code=303)
    response.set_cookie(web.SESSION_COOKIE, token, httponly=True, samesite="lax", path="/")
    return response
