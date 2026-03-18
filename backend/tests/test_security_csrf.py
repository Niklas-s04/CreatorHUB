from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token, create_csrf_token
from app.core.web_security import CsrfProtectionMiddleware


def _build_csrf_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CsrfProtectionMiddleware,
        auth_cookie_name=settings.AUTH_ACCESS_COOKIE_NAME,
        csrf_cookie_name=settings.CSRF_COOKIE_NAME,
    )

    @app.post("/api/protected")
    def protected() -> dict[str, str]:
        return {"ok": "true"}

    @app.post("/api/auth/token")
    def login_exempt() -> dict[str, str]:
        return {"ok": "true"}

    return app


def _access_cookie_for_sid(session_id: str) -> str:
    return create_access_token(
        subject="csrf-user", role="editor", session_id=session_id, jti="csrf-jti"
    )


def test_csrf_skips_auth_token_endpoint() -> None:
    app = _build_csrf_app()
    client = TestClient(app)

    response = client.post("/api/auth/token")
    assert response.status_code == 200


def test_csrf_blocks_missing_header_when_authenticated() -> None:
    app = _build_csrf_app()
    client = TestClient(app)

    sid = str(uuid.uuid4())
    client.cookies.set(settings.AUTH_ACCESS_COOKIE_NAME, _access_cookie_for_sid(sid))
    client.cookies.set(settings.CSRF_COOKIE_NAME, create_csrf_token(sid))

    response = client.post("/api/protected")
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_csrf_allows_valid_cookie_and_header() -> None:
    app = _build_csrf_app()
    client = TestClient(app)

    sid = str(uuid.uuid4())
    csrf = create_csrf_token(sid)
    client.cookies.set(settings.AUTH_ACCESS_COOKIE_NAME, _access_cookie_for_sid(sid))
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf)

    response = client.post("/api/protected", headers={"x-csrf-token": csrf})
    assert response.status_code == 200


def test_csrf_blocks_invalid_signature_token() -> None:
    app = _build_csrf_app()
    client = TestClient(app)

    sid = str(uuid.uuid4())
    csrf_cookie = create_csrf_token(sid)
    forged_csrf = csrf_cookie.rsplit(".", 1)[0] + ".forged"

    client.cookies.set(settings.AUTH_ACCESS_COOKIE_NAME, _access_cookie_for_sid(sid))
    client.cookies.set(settings.CSRF_COOKIE_NAME, forged_csrf)

    response = client.post("/api/protected", headers={"x-csrf-token": forged_csrf})
    assert response.status_code == 403
