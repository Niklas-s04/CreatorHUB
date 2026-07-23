from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, model_validator

from app.api.error_handlers import install_error_handlers


class _ValidatedPayload(BaseModel):
    value: int

    @model_validator(mode="after")
    def reject_negative_value(self) -> "_ValidatedPayload":
        if self.value < 0:
            raise ValueError("value must not be negative")
        return self


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/boom")
    def boom() -> dict[str, str]:
        raise HTTPException(status_code=409, detail={"message": "Conflict"})

    @app.get("/validation")
    def validation(value: int) -> dict[str, int]:
        return {"value": value}

    @app.post("/model-validation")
    def model_validation(payload: _ValidatedPayload) -> dict[str, int]:
        return {"value": payload.value}

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


def test_validation_error_context_is_json_serializable() -> None:
    app = _build_app()
    with TestClient(app) as client:
        response = client.post("/model-validation", json={"value": -1})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"][0]["ctx"]["error"] == "value must not be negative"


def test_unhandled_exception_handler_returns_error_payload() -> None:
    app = _build_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/error")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert body["message"] == "Internal server error"
