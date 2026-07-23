from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.api_errors import api_error_response

logger = logging.getLogger("app.api.errors")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        status_code = int(exc.status_code)
        detail = exc.detail
        logger.log(
            logging.WARNING if status_code < 500 else logging.ERROR,
            "HTTP exception handled",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "status_code": status_code,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return api_error_response(
            status_code=status_code,
            message=(
                str(detail) if not isinstance(detail, dict) else str(detail.get("message", detail))
            ),
            details=detail if isinstance(detail, (dict, list)) else None,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "Request validation failed",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "status_code": 422,
                "path": request.url.path,
                "method": request.method,
                "error_count": len(exc.errors()),
            },
        )
        return api_error_response(
            status_code=422,
            message="Request validation failed",
            details=list(exc.errors()),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, _: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled API exception",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "status_code": 500,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return api_error_response(
            status_code=500,
            message="Internal server error",
            details=None,
        )
