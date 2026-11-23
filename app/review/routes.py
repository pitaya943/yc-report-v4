from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.core import web
from app.core.permissions import Actor, authorize, permission

router = APIRouter()


@permission("review.open")
def _administrators_only(actor: Actor, resource: object | None) -> bool:
    return actor.role in ("ADMIN", "OWNER")


@router.get("/review")
def review_page(request: Request, actor: Actor = Depends(web.current_actor)) -> Response:
    authorize(actor, "review.open")
    return web.render(request, "review/placeholder.html")
