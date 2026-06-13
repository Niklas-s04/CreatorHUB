from __future__ import annotations

import pytest

from app.core.config import settings
from app.main import _validate_security_settings


def test_prod_requires_explicit_cookie_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "prod")
    monkeypatch.setattr(settings, "JWT_SECRET", "x" * 64)
    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", True)
    monkeypatch.setattr(settings, "AUTH_COOKIE_DOMAIN", None)
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setattr(settings, "AUTH_COOKIE_SAMESITE", "strict")

    with pytest.raises(
        RuntimeError, match="AUTH_COOKIE_DOMAIN must be explicitly set in production"
    ):
        _validate_security_settings()


def test_prod_allows_cookie_domain_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "prod")
    monkeypatch.setattr(settings, "JWT_SECRET", "x" * 64)
    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", True)
    monkeypatch.setattr(settings, "AUTH_COOKIE_SAMESITE", "strict")
    monkeypatch.setattr(settings, "AUTH_COOKIE_DOMAIN", "creatorhub.example.com")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setattr(settings, "SECURITY_SENSITIVE_ACTION_REQUIRE_STEP_UP_MFA", True)

    _validate_security_settings()


def test_prod_requires_step_up_mfa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "prod")
    monkeypatch.setattr(settings, "JWT_SECRET", "x" * 64)
    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", True)
    monkeypatch.setattr(settings, "AUTH_COOKIE_SAMESITE", "strict")
    monkeypatch.setattr(settings, "AUTH_COOKIE_DOMAIN", "creatorhub.example.com")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setattr(settings, "SECURITY_SENSITIVE_ACTION_REQUIRE_STEP_UP_MFA", False)

    with pytest.raises(
        RuntimeError,
        match="SECURITY_SENSITIVE_ACTION_REQUIRE_STEP_UP_MFA must be true in production",
    ):
        _validate_security_settings()


def test_security_defaults_match_release_policy() -> None:
    assert settings.AUTH_COOKIE_SAMESITE == "strict"
    assert settings.SESSION_IDLE_TIMEOUT_MINUTES == 30
    assert settings.SESSION_ABSOLUTE_TIMEOUT_MINUTES == 60 * 24 * 7
    assert settings.JWT_REFRESH_EXPIRE_MINUTES == 60 * 24 * 7
