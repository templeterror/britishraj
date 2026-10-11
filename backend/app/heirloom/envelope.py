from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException


class Meta(BaseModel):
    revision: int = 0
    consent_revision: int = 0
    mode: Literal["demo", "clerk"]
    degraded: list[str] = Field(default_factory=list)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def ok(data: Any, meta: Meta) -> dict:
    return {"data": data, "meta": meta.model_dump(), "errors": []}


_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
}


def _error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    settings = getattr(request.app.state, "settings", None)
    meta = Meta(mode=settings.mode if settings else "demo")
    body = {"data": None, "meta": meta.model_dump(), "errors": [{"code": code, "message": message}]}
    return JSONResponse(status_code=status, content=body)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _error_response(request, exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return _error_response(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
        return _error_response(request, 422, "validation_error", f"Invalid request: {fields}")
