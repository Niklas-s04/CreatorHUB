from __future__ import annotations

import json
import logging
import logging.config
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import Settings
from app.services.policy_checks import redact_sensitive

REQUEST_ID_HEADER = "x-request-id"

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_ALLOWED_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._\-]{8,128}$")
_SENSITIVE_FIELD_NAMES = {
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
    "refresh_token",
    "access_token",
    "api_key",
    "set-cookie",
    "cookie",
    "csrf",
    "email",
    "phone",
    "iban",
    "card",
}

_RESERVED_LOG_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def _normalize_request_id(raw: str | None) -> str:
    candidate = (raw or "").strip()
    if candidate and _ALLOWED_REQUEST_ID_RE.fullmatch(candidate):
        return candidate
    return str(uuid.uuid4())


def _sanitize_key(key: str) -> str:
    return (key or "").strip().lower().replace("-", "_")


def _mask_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return redact_sensitive(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, raw_val in value.items():
            normalized_key = _sanitize_key(str(key))
            if any(sensitive in normalized_key for sensitive in _SENSITIVE_FIELD_NAMES):
                out[str(key)] = "[REDACTED]"
            else:
                out[str(key)] = _mask_value(raw_val)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_mask_value(item) for item in value]
    return redact_sensitive(str(value))


class RequestIdContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive(message),
            "request_id": getattr(record, "request_id", None) or get_request_id(),
        }

        extra: dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_ATTRS:
                continue
            extra[key] = _mask_value(value)
        if extra:
            payload["context"] = extra

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


class RequestContextLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("app.request")

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = _normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = _request_id_ctx.set(request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            self.logger.exception(
                "Unhandled request error",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            _request_id_ctx.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        level = logging.ERROR if status_code >= 500 else logging.WARNING if status_code >= 400 else logging.INFO
        self.logger.log(
            level,
            "HTTP request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


def log_security_event(
    event: str,
    *,
    level: int = logging.WARNING,
    request: Request | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    logger = logging.getLogger("app.security")
    request_id = None
    path = None
    method = None
    client_ip = None

    if request is not None:
        request_id = getattr(request.state, "request_id", None) or request.headers.get(REQUEST_ID_HEADER)
        path = request.url.path
        method = request.method
        if request.client and request.client.host:
            client_ip = request.client.host

    logger.log(
        level,
        "Security event",
        extra={
            "request_id": request_id,
            "security_event": True,
            "event": event,
            "path": path,
            "method": method,
            "client_ip": client_ip,
            "details": details or {},
        },
    )


def _log_level(level_name: str) -> int:
    return getattr(logging, (level_name or "INFO").strip().upper(), logging.INFO)


def _build_formatter(settings: Settings) -> logging.Formatter:
    log_format = (settings.LOG_FORMAT or "json").strip().lower()
    if log_format == "json":
        return JsonLogFormatter()
    return logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def _build_stream_handler(settings: Settings) -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_build_formatter(settings))
    handler.addFilter(RequestIdContextFilter())
    return handler


def _build_file_handler(log_path: Path, retention_days: int, settings: Settings) -> logging.Handler:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        filename=str(log_path),
        when="midnight",
        interval=1,
        backupCount=max(1, retention_days),
        encoding="utf-8",
        utc=True,
    )
    handler.setFormatter(_build_formatter(settings))
    handler.addFilter(RequestIdContextFilter())
    return handler


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    security_logger = logging.getLogger("app.security")
    for handler in list(security_logger.handlers):
        security_logger.removeHandler(handler)
        handler.close()

    app_level = _log_level(settings.LOG_LEVEL)
    root.setLevel(app_level)

    handlers: list[logging.Handler] = []
    if settings.LOG_TO_STDOUT:
        handlers.append(_build_stream_handler(settings))
    if settings.LOG_TO_FILE:
        base_dir = Path(settings.LOG_DIR)
        handlers.append(
            _build_file_handler(base_dir / settings.LOG_FILE_NAME, settings.LOG_RETENTION_DAYS, settings)
        )

    if not handlers:
        handlers.append(_build_stream_handler(settings))

    for handler in handlers:
        root.addHandler(handler)

    security_logger.setLevel(_log_level(settings.SECURITY_LOG_LEVEL))
    security_logger.propagate = True

    if settings.LOG_TO_FILE and settings.SECURITY_LOG_TO_SEPARATE_FILE:
        security_logger.addHandler(
            _build_file_handler(
                Path(settings.LOG_DIR) / settings.SECURITY_LOG_FILE_NAME,
                settings.SECURITY_LOG_RETENTION_DAYS,
                settings,
            )
        )
        security_logger.propagate = settings.SECURITY_LOG_PROPAGATE_TO_ROOT

    logging.getLogger("uvicorn").setLevel(_log_level(settings.UVICORN_LOG_LEVEL))
    logging.getLogger("uvicorn.error").setLevel(_log_level(settings.UVICORN_LOG_LEVEL))
    logging.getLogger("uvicorn.access").setLevel(_log_level(settings.UVICORN_ACCESS_LOG_LEVEL))
