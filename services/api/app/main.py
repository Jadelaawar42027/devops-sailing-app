"""App factory. Run with: uvicorn app.main:create_app --factory"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, load_settings
from app.logging_setup import add_request_logging, configure_logging
from app.routers import health


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings.service_name, settings.log_level)

    app = FastAPI(title="Sailing Planner API", version=settings.version)
    app.state.settings = settings

    # CORS restricted to the UI origin (brief §3a).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )
    add_request_logging(app)

    app.include_router(health.router)
    return app
