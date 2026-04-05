"""Security headers validation tests."""

from __future__ import annotations


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


def test_cors_no_wildcard_credentials(client) -> None:
    """Verify CORS doesn't allow wildcards with credentials."""
    response = client.post("/api/auth/token", data={"username": "test", "password": "test"})
    allow_origin = response.headers.get("Access-Control-Allow-Origin", "")
    allow_creds = response.headers.get("Access-Control-Allow-Credentials", "")

    if allow_creds and allow_creds.lower() == "true":
        assert allow_origin != "*", "Cannot use wildcard with credentials"
