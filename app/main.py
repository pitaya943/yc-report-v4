import importlib
import importlib.util
import pkgutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import app as app_package
from app.accounts.passwords import Passwords
from app.core import outcomes, web
from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import Database, TransactionMiddleware


def _include_domain_routes(application: FastAPI) -> None:
    """Every package under app/ that has a ``routes`` module contributes its ``router``."""
    for package in pkgutil.iter_modules(app_package.__path__):
        name = f"app.{package.name}.routes"
        if package.ispkg and importlib.util.find_spec(name) is not None:
            application.include_router(importlib.import_module(name).router)


def create_app(settings: Settings, clock: Clock) -> FastAPI:
    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database.open()
        try:
            yield
        finally:
            database.close()

    application = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    application.state.settings = settings
    application.state.clock = clock
    application.state.database = database
    application.state.passwords = Passwords(settings.password_hash_profile)

    application.add_middleware(TransactionMiddleware, database=database)
    outcomes.install(application, page=web.refusal_page)
    _include_domain_routes(application)
    application.mount("/static", StaticFiles(directory=web.STATIC_DIR))
    return application
