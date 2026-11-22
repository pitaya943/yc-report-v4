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


async def _form(request: Request) -> FormData:
    return await request.form()


def _text(form: FormData, field: str) -> str | None:
    value = form.get(field)
    return value if isinstance(value, str) else None


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
