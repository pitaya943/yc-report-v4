import ipaddress

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from psycopg import Connection
from starlette.datastructures import FormData

from app.accounts import service
from app.core import web
from app.core.db import connection
from app.core.permissions import Actor

router = APIRouter()

# In the address of the sign-in page a person is sent to after signing out.
SIGNED_OUT = "signed-out"
# An IPv6 address written out in full with an IPv4 tail.
_LONGEST_ADDRESS = 45


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
    is counted under its peer, and so is one whose value there is not an IP
    address: a proxy writes nothing else, and the address is stored and
    indexed, so it has to be short.
    """
    peer = request.client.host if request.client else "unknown"
    hops = request.app.state.settings.trusted_proxy_hops
    forwarded = [value.strip() for value in ",".join(request.headers.getlist("x-forwarded-for")).split(",")]
    if hops == 0 or len(forwarded) < hops or len(forwarded[-hops]) > _LONGEST_ADDRESS:
        return peer
    try:
        return str(ipaddress.ip_address(forwarded[-hops]))
    except ValueError:
        return peer


@router.get("/")
def front_door(request: Request) -> Response:
    actor = web.signed_in_actor(request)
    return RedirectResponse(service.LANDING_PAGES[actor.role] if actor else "/sign-in", status_code=303)


@router.get("/sign-in")
def sign_in_page(request: Request) -> Response:
    actor = web.signed_in_actor(request)
    if actor:
        return RedirectResponse(service.LANDING_PAGES[actor.role], status_code=303)
    return web.sign_in_page(request, notice="您已登出" if SIGNED_OUT in request.query_params else None)


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
    # No Max-Age and no Expires: the cookie goes when the browser closes.
    response.set_cookie(
        web.SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        path="/",
        secure=request.app.state.settings.app_env == "production",
    )
    return response


@router.post("/sign-out")
def sign_out(
    request: Request, actor: Actor = Depends(web.current_actor), conn: Connection = Depends(connection)
) -> Response:
    service.sign_out(conn, request.app.state.clock, web.session_of(request))
    response = RedirectResponse(f"/sign-in?{SIGNED_OUT}", status_code=303)
    response.delete_cookie(web.SESSION_COOKIE, path="/")
    return response
