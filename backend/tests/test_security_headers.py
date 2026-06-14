"""Security headers validation tests."""

from __future__ import annotations

from app.core.config import settings
from app.models.user import UserRole
from tests.factories import DEFAULT_PASSWORD, create_user


def test_csp_has_required_directives(client) -> None:
    """Verify CSP includes essential security directives."""
    response = client.post("/api/auth/token", data={"username": "test", "password": "test"})
    csp = response.headers.get("Content-Security-Policy", "")

    if csp:
        required_directives = [
            "default-src 'none'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self'",
            "frame-ancestors 'none'",
            "object-src 'none'",
            "form-action 'self'",
            "upgrade-insecure-requests",
        ]
        for directive in required_directives:
            assert directive in csp, f"CSP missing: {directive}"


def test_csp_no_unsafe_inline(client) -> None:
    """Verify CSP does not contain unsafe values."""
    response = client.post("/api/auth/token", data={"username": "test", "password": "test"})
    csp = response.headers.get("Content-Security-Policy", "")
    if csp:
        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp


def test_security_headers_present(client) -> None:
    """Verify essential security headers are present."""
    response = client.post("/api/auth/token", data={"username": "test", "password": "test"})
    csp = response.headers.get("Content-Security-Policy", "")
    assert csp, "CSP header must be present"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
    assert response.headers.get("Cross-Origin-Embedder-Policy") == "require-corp"
    assert response.headers.get("Cross-Origin-Resource-Policy") == "same-origin"


def test_x_content_type_options_nosniff(client) -> None:
    response = client.get("/health/ready")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"


def test_x_frame_options_deny(client) -> None:
    response = client.get("/health/ready")
    assert response.headers.get("X-Frame-Options") == "DENY"


def test_hsts_preload_present(client) -> None:
    response = client.get("/health/ready", headers={"x-forwarded-proto": "https"})
    hsts = response.headers.get("Strict-Transport-Security", "")
    if settings.ENV == "prod":
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts


def test_cors_config_valid(client) -> None:
    response = client.options(
        "/api/auth/token",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("Access-Control-Allow-Origin") != "*"


def test_cors_no_wildcard_credentials(client) -> None:
    """Verify CORS doesn't allow wildcards with credentials."""
    response = client.post("/api/auth/token", data={"username": "test", "password": "test"})
    allow_origin = response.headers.get("Access-Control-Allow-Origin", "")
    allow_creds = response.headers.get("Access-Control-Allow-Credentials", "")

    if allow_creds and allow_creds.lower() == "true":
        assert allow_origin != "*", "Cannot use wildcard with credentials"


def test_auth_cookie_flags_strict_secure_domain(client, db_session, monkeypatch) -> None:
    user = create_user(db_session, username="cookie_flags_user", role=UserRole.editor)
    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", True)
    monkeypatch.setattr(settings, "AUTH_COOKIE_SAMESITE", "strict")

    response = client.post(
        "/api/auth/token",
        data={"username": user.username, "password": DEFAULT_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    set_cookie_values = response.headers.get_list("set-cookie")
    access_cookie = next(
        value
        for value in set_cookie_values
        if value.startswith(f"{settings.AUTH_ACCESS_COOKIE_NAME}=")
    )
    csrf_cookie = next(
        value for value in set_cookie_values if value.startswith(f"{settings.CSRF_COOKIE_NAME}=")
    )
    assert "HttpOnly" in access_cookie
    assert "Secure" in access_cookie
    assert "SameSite=strict" in access_cookie
    assert f"Domain={settings.AUTH_COOKIE_DOMAIN}" in access_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "Secure" in csrf_cookie
    assert "SameSite=strict" in csrf_cookie
