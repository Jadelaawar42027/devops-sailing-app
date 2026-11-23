import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.errors import add_error_handlers
from app.logging_middleware import add_request_logging, configure_logging
from app.migrations import run_migrations
from app.settings import get_settings

logger = logging.getLogger("passage-api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.db_connection_string:
        run_migrations(settings.db_connection_string, create_db=settings.db_create_if_missing)
    else:
        logger.warning("DB_CONNECTION_STRING not set: skipping migrations (tests / no-DB mode)")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="passage-api", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )
    add_request_logging(app)
    add_error_handlers(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Routers go here as they land:
    # app.include_router(boats.router)
    # app.include_router(passages.router)
    return app


app = create_app()