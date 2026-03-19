from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.common import ErrorResponse

STATUS_CODE_TO_ERROR_CODE = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _error_code_for_status(status_code: int) -> str:
    return STATUS_CODE_TO_ERROR_CODE.get(status_code, "API_ERROR")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        status_code = int(exc.status_code)
        detail = exc.detail
        payload = ErrorResponse(
            code=_error_code_for_status(status_code),
            message=str(detail)
            if not isinstance(detail, dict)
            else str(detail.get("message", detail)),
            status=status_code,
            details=detail if isinstance(detail, (dict, list)) else None,
        )
        return JSONResponse(status_code=status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        payload = ErrorResponse(
            code=_error_code_for_status(422),
            message="Request validation failed",
            status=422,
            details=exc.errors(),
        )
        return JSONResponse(status_code=422, content=payload.model_dump())
