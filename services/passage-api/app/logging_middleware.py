import json
import logging
import time

from fastapi import FastAPI, Request

logger = logging.getLogger("passage-api.requests")


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(message)s", force=True)


def add_request_logging(app: FastAPI) -> None:
    """One JSON line per request. Logs the route template, never bodies."""

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = route.path if route else request.url.path  # "/boats/{id}", not "/boats/42"
        logger.info(
            json.dumps(
                {
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                }
            )
        )
        return response