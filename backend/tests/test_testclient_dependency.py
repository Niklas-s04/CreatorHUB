from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_fastapi_testclient_serves_basic_route() -> None:
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "true"}

    response = TestClient(app).get("/ping")

    assert response.status_code == 200
    assert response.json() == {"ok": "true"}
