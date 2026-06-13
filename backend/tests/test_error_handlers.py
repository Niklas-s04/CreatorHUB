from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.error_handlers import install_error_handlers


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/boom")
    def boom() -> dict[str, str]:
        raise HTTPException(status_code=409, detail={"message": "Conflict"})

    @app.get("/validation")
    def validation(value: int) -> dict[str, int]:
        return {"value": value}

    @app.get("/error")
    def error() -> dict[str, str]:
        raise RuntimeError("boom")

    install_error_handlers(app)
    return app


def test_http_exception_handler_returns_error_payload() -> None:
    app = _build_app()
    with TestClient(app) as client:
        response = client.get("/boom")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "CONFLICT"
    assert body["message"] == "Conflict"
    assert body["status"] == 409


def test_validation_exception_handler_returns_error_payload() -> None:
    app = _build_app()
    with TestClient(app) as client:
        response = client.get("/validation", params={"value": "not-a-number"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Request validation failed"
    assert isinstance(body["details"], list)


def test_unhandled_exception_handler_returns_error_payload() -> None:
    app = _build_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/error")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert body["message"] == "Internal server error"
