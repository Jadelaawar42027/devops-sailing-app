"""Every error leaves the API as {"error": "<human message>", "code": "<MACHINE_CODE>"}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("passage-api.errors")

DEFAULT_CODES = {
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def error_body(message: str, code: str) -> dict:
    return {"error": message, "code": code}


def add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return JSONResponse(error_body(exc.message, exc.code), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        code = DEFAULT_CODES.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(error_body(str(exc.detail), code), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = f"{field}: {first.get('msg', 'invalid input')}" if field else "Invalid input"
        return JSONResponse(error_body(message, "VALIDATION_ERROR"), status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        logger.exception("Unhandled error")
        return JSONResponse(error_body("Internal server error", "INTERNAL_ERROR"), status_code=500)