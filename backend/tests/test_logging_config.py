from __future__ import annotations

import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging_config import (
    JsonLogFormatter,
    RequestContextLoggingMiddleware,
    configure_logging,
    log_security_event,
)


def test_json_formatter_redacts_sensitive_fields() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="User alice@example.com tried token secret-value",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-12345678"
    record.details = {
        "password": "cleartext",
        "email": "alice@example.com",
        "nested": {"api_key": "abc123"},
    }

    payload = json.loads(formatter.format(record))

    assert payload["request_id"] == "req-12345678"
    assert "[EMAIL_REDACTED]" in payload["message"]
    assert payload["context"]["details"]["password"] == "[REDACTED]"
    assert payload["context"]["details"]["email"] == "[REDACTED]"
    assert payload["context"]["details"]["nested"]["api_key"] == "[REDACTED]"


def test_request_context_middleware_sets_and_returns_request_id(caplog) -> None:
    app = FastAPI()
    app.add_middleware(RequestContextLoggingMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "true"}

    with caplog.at_level(logging.INFO, logger="app.request"):
        response = TestClient(app).get("/ping", headers={"x-request-id": "req-id-12345"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-id-12345"
    assert any(getattr(rec, "request_id", None) == "req-id-12345" for rec in caplog.records)


def test_security_event_logging_uses_request_context(caplog) -> None:
    app = FastAPI()
    app.add_middleware(RequestContextLoggingMiddleware)

    @app.get("/security")
    def security_check(request: Request) -> dict[str, str]:
        log_security_event(
            "csrf_validation_failed",
            request=request,
            details={"token": "abc", "email": "a@example.com"},
        )
        return {"ok": "true"}

    with caplog.at_level(logging.WARNING, logger="app.security"):
        response = TestClient(app).get("/security")

    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert any(getattr(rec, "security_event", False) is True for rec in caplog.records)


def test_configure_logging_applies_retention_to_file_handlers(tmp_path: Path) -> None:
    settings = Settings(
        LOG_TO_STDOUT=False,
        LOG_TO_FILE=True,
        LOG_DIR=str(tmp_path),
        LOG_FILE_NAME="app.log",
        LOG_RETENTION_DAYS=14,
        SECURITY_LOG_TO_SEPARATE_FILE=True,
        SECURITY_LOG_FILE_NAME="security.log",
        SECURITY_LOG_RETENTION_DAYS=120,
    )

    configure_logging(settings)

    root_handlers = [h for h in logging.getLogger().handlers if isinstance(h, TimedRotatingFileHandler)]
    assert any(Path(handler.baseFilename).name == "app.log" for handler in root_handlers)
    assert any(handler.backupCount == 14 for handler in root_handlers)

    security_handlers = [
        h for h in logging.getLogger("app.security").handlers if isinstance(h, TimedRotatingFileHandler)
    ]
    assert any(Path(handler.baseFilename).name == "security.log" for handler in security_handlers)
    assert any(handler.backupCount == 120 for handler in security_handlers)
