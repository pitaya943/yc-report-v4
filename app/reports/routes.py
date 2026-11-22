from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.core import web
from app.core.permissions import Actor, authorize, permission

router = APIRouter()


@permission("reports.open")
def _users_only(actor: Actor, resource: object | None) -> bool:
    return actor.role == "USER"


@router.get("/reports")
def reports_page(request: Request, actor: Actor = Depends(web.current_actor)) -> Response:
    authorize(actor, "reports.open")
    return web.render(request, "reports/placeholder.html")
