from __future__ import annotations

from typing import Any

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


def error_code_for_status(status_code: int) -> str:
    return STATUS_CODE_TO_ERROR_CODE.get(status_code, "API_ERROR")


def api_error_payload(
    *,
    status_code: int,
    message: str,
    details: dict[str, Any] | list[Any] | str | None = None,
) -> dict[str, Any]:
    return ErrorResponse(
        code=error_code_for_status(status_code),
        message=message,
        status=status_code,
        details=details,
    ).model_dump(mode="json", fallback=str)


def api_error_response(
    *,
    status_code: int,
    message: str,
    details: dict[str, Any] | list[Any] | str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=api_error_payload(
            status_code=status_code,
            message=message,
            details=details,
        ),
    )
