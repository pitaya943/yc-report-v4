from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from psycopg import Connection

from app.core import migrate, web
from app.core.db import connection
from app.core.permissions import Actor, authorize, permission

router = APIRouter()


@permission("system.status")
def _administrators_and_the_owner(actor: Actor, resource: object | None) -> bool:
    return actor.role in ("ADMIN", "OWNER")


@router.get("/health")
def health(request: Request) -> JSONResponse:
    """For the platform: does the database answer? No detail either way."""
    if request.app.state.database.ping():
        return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "unavailable"}, status_code=503)


@router.get("/status")
def status_page(
    request: Request, actor: Actor = Depends(web.current_actor), conn: Connection = Depends(connection)
) -> Response:
    authorize(actor, "system.status")
    settings = request.app.state.settings
    return web.render(
        request,
        "system/status.html",
        # This page is only reached through the database: the session was read from it.
        migration_version=f"{migrate.applied_version(conn):04d}",
        storage_configured=settings.storage_configured,
        bank_key_configured=settings.bank_key_configured,
    )
