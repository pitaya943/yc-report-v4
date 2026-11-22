from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health(request: Request) -> JSONResponse:
    """For the platform: does the database answer? No detail either way."""
    if request.app.state.database.ping():
        return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "unavailable"}, status_code=503)
