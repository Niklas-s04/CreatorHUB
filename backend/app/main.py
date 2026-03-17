from __future__ import annotations

import asyncio
from contextlib import suppress
from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.web_security import SecurityHeadersMiddleware, RequestSizeLimitMiddleware, RateLimitMiddleware, CsrfProtectionMiddleware
from app.api.routers import auth, products, assets, content, email, images, knowledge, health, deals, audit
from app.seed import bootstrap_if_needed
from app.services.auto_archive import auto_archive_daemon


def _validate_security_settings() -> None:
    if settings.ENV.lower() == "prod" and settings.JWT_SECRET == "change_me":
        raise RuntimeError("JWT_SECRET must be set to a strong value in production")

    if settings.ENV.lower() == "prod":
        if not settings.AUTH_COOKIE_SECURE:
            raise RuntimeError("AUTH_COOKIE_SECURE must be true in production")
        origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
        if any(o == "*" for o in origins):
            raise RuntimeError("CORS wildcard is not allowed in production")

    if settings.AUTH_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
        raise RuntimeError("AUTH_COOKIE_SAMESITE must be one of: lax, strict, none")
    if settings.AUTH_COOKIE_SAMESITE == "none" and not settings.AUTH_COOKIE_SECURE:
        raise RuntimeError("AUTH_COOKIE_SECURE must be true when AUTH_COOKIE_SAMESITE=none")


def _validate_runtime_config() -> None:
    def _require_url(name: str, value: str, allowed_schemes: set[str]) -> None:
        parsed = urlparse((value or "").strip())
        if not parsed.scheme or parsed.scheme not in allowed_schemes:
            raise RuntimeError(f"{name} must use one of schemes: {', '.join(sorted(allowed_schemes))}")
        if not parsed.netloc:
            raise RuntimeError(f"{name} must include host information")

    _require_url("DATABASE_URL", settings.DATABASE_URL, {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"})
    _require_url("REDIS_URL", settings.REDIS_URL, {"redis", "rediss"})
    _require_url("OLLAMA_URL", settings.OLLAMA_URL, {"http", "https"})

    if not (settings.PROJECT_NAME or "").strip():
        raise RuntimeError("PROJECT_NAME must not be empty")
    if not (settings.CORS_ORIGINS or "").strip():
        raise RuntimeError("CORS_ORIGINS must not be empty")
    if settings.SECURITY_HSTS_SECONDS < 0:
        raise RuntimeError("SECURITY_HSTS_SECONDS must be >= 0")

    if settings.ENV.lower() == "prod":
        if (settings.BOOTSTRAP_INSTALL_TOKEN or "").strip() == "":
            raise RuntimeError("BOOTSTRAP_INSTALL_TOKEN must be set in production")
        if settings.BOOTSTRAP_ADMIN_PASSWORD == "admin":
            raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD default is not allowed in production")


def create_app() -> FastAPI:
    _validate_runtime_config()
    _validate_security_settings()
    app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

    trusted_hosts = [h.strip() for h in settings.TRUSTED_HOSTS.split(",") if h.strip()]
    if trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

    app.add_middleware(RequestSizeLimitMiddleware, max_body_size=settings.MAX_REQUEST_BODY_BYTES)
    app.add_middleware(
        CsrfProtectionMiddleware,
        auth_cookie_name=settings.AUTH_ACCESS_COOKIE_NAME,
        csrf_cookie_name=settings.CSRF_COOKIE_NAME,
    )
    if settings.RATE_LIMIT_ENABLED:
        app.add_middleware(
            RateLimitMiddleware,
            redis_url=settings.REDIS_URL,
            redis_prefix=settings.RATE_LIMIT_REDIS_PREFIX,
            trust_proxy_headers=settings.TRUST_PROXY_HEADERS,
            global_limit=settings.RATE_LIMIT_GLOBAL,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
            auth_limit=settings.RATE_LIMIT_AUTH,
        )
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_seconds=settings.SECURITY_HSTS_SECONDS,
        trust_proxy_headers=settings.TRUST_PROXY_HEADERS,
        env=settings.ENV,
    )

    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(products.router, prefix="/api/products", tags=["products"])
    app.include_router(assets.router, prefix="/api/assets", tags=["assets"])
    app.include_router(content.router, prefix="/api/content", tags=["content"])
    app.include_router(email.router, prefix="/api/email", tags=["email"])
    app.include_router(images.router, prefix="/api/images", tags=["images"])
    app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
    app.include_router(deals.router, prefix="/api/deals", tags=["deals"])
    app.include_router(audit.router, prefix="/api/audit", tags=["audit"])

    @app.on_event("startup")
    def _startup() -> None:
        bootstrap_if_needed()
        app.state.auto_archive_task = None
        if settings.AUTO_ARCHIVE_ENABLED:
            loop = asyncio.get_event_loop()
            app.state.auto_archive_task = loop.create_task(auto_archive_daemon())

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        task = getattr(app.state, "auto_archive_task", None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
