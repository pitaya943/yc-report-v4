"""A FastAPI app whose every process runs the trigger loop. Configuration only:
DATABASE_URL and TICK_SECONDS."""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .clock import SystemClock
from .jobs import tick
from .trigger import run_forever


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.environ["DATABASE_URL"]
    interval = float(os.environ.get("TICK_SECONDS", "30"))
    clock = SystemClock()
    loop = asyncio.create_task(run_forever(lambda: tick(database_url, clock), interval))
    yield
    loop.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True}
