"""App factory. Run with: uvicorn app.main:create_app --factory"""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.config import Settings, load_settings
from app.db import make_engine, prepare_database
from app.logging_setup import add_request_logging, configure_logging
from app.routers import boats, health, passages, windows

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, http: httpx.Client | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings.service_name, settings.log_level)
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.run_migrations:
            prepare_database(settings, engine)
        yield
        app.state.http.close()
        engine.dispose()

    app = FastAPI(title="Sailing Planner API", version=settings.version, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.state.http = http or httpx.Client(headers={"User-Agent": "sailing-planner-api/1.0"})

    # CORS restricted to the UI origin (brief §3a).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )
    add_request_logging(app)

    @app.exception_handler(OperationalError)
    async def database_unavailable(request: Request, exc: OperationalError):
        log.warning("database unavailable", extra={"fields": {"error": type(exc).__name__}})
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable, please retry in a few seconds."},
        )

    app.include_router(health.router)
    app.include_router(boats.router)
    app.include_router(passages.router)
    app.include_router(windows.router)
    return app
