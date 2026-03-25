from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.error_handlers import install_error_handlers
from app.api.routers import (
    assets,
    audit,
    auth,
    content,
    dashboard,
    deals,
    email,
    health,
    images,
    knowledge,
    operations,
    products,
    search,
)
from app.core.config import settings
from app.core.web_security import (
    CsrfProtectionMiddleware,
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.session import engine
from app.schemas.common import ErrorResponse
from app.seed import bootstrap_if_needed
from app.services.auto_archive import auto_archive_daemon

logger = logging.getLogger(__name__)

API_VERSION = "v1"
API_BASE_PREFIX = f"/api/{API_VERSION}"
LEGACY_API_PREFIX = "/api"


def _close_redis_client(redis_client: Redis | None) -> None:
    if redis_client is None:
        return
    with suppress(Exception):
        redis_client.close()
    with suppress(Exception):
        redis_client.connection_pool.disconnect()


def _close_worker_redis_connection() -> None:
    with suppress(Exception):
        from app.workers.queue import redis_conn

        redis_conn.close()
        redis_conn.connection_pool.disconnect()


def _initialize_runtime_resources(app: FastAPI) -> None:
    app.state.startup_complete = False
    app.state.bootstrap_complete = False
    app.state.auto_archive_task = None
    app.state.redis_client = None

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    redis_client.ping()
    app.state.redis_client = redis_client

    bootstrap_if_needed()
    app.state.bootstrap_complete = True

    if settings.AUTO_ARCHIVE_ENABLED:
        loop = asyncio.get_running_loop()
        app.state.auto_archive_task = loop.create_task(auto_archive_daemon())

    app.state.startup_complete = True


async def _shutdown_runtime_resources(app: FastAPI) -> None:
    task = getattr(app.state, "auto_archive_task", None)
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    _close_worker_redis_connection()

    redis_client = getattr(app.state, "redis_client", None)
    _close_redis_client(redis_client)
    app.state.redis_client = None

    with suppress(Exception):
        engine.dispose()

    app.state.startup_complete = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        _initialize_runtime_resources(app)
    except Exception:
        logger.exception("Application initialization failed. Aborting startup.")
        await _shutdown_runtime_resources(app)
        raise

    try:
        yield
    finally:
        await _shutdown_runtime_resources(app)


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
            raise RuntimeError(
                f"{name} must use one of schemes: {', '.join(sorted(allowed_schemes))}"
            )
        if not parsed.netloc:
            raise RuntimeError(f"{name} must include host information")

    _require_url(
        "DATABASE_URL",
        settings.DATABASE_URL,
        {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"},
    )
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
    try:
        _validate_runtime_config()
        _validate_security_settings()
    except Exception:
        logger.exception("Invalid runtime/security configuration detected")
        raise

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        lifespan=lifespan,
        description=(
            "CreatorHUB Backend API. Stable versioned endpoints are available under "
            f"{API_BASE_PREFIX}. Legacy {LEGACY_API_PREFIX} endpoints remain temporarily available"
            " and are marked as deprecated in OpenAPI."
        ),
        responses={
            400: {"model": ErrorResponse, "description": "Bad request"},
            401: {"model": ErrorResponse, "description": "Unauthorized"},
            403: {"model": ErrorResponse, "description": "Forbidden"},
            404: {"model": ErrorResponse, "description": "Not found"},
            409: {"model": ErrorResponse, "description": "Conflict"},
            422: {"model": ErrorResponse, "description": "Validation error"},
            500: {"model": ErrorResponse, "description": "Internal server error"},
            503: {"model": ErrorResponse, "description": "Service unavailable"},
        },
        openapi_tags=[
            {"name": "health", "description": "Liveness, readiness, and runtime health state"},
            {"name": "auth", "description": "Authentication, sessions, MFA, and registration"},
            {
                "name": "products",
                "description": "Inventory products, lifecycle, values, transactions",
            },
            {"name": "assets", "description": "Asset upload, review workflow, and library access"},
            {"name": "content", "description": "Content planning items and production tasks"},
            {"name": "email", "description": "Email thread assistant and draft workflow"},
            {"name": "images", "description": "Async image search jobs"},
            {"name": "knowledge", "description": "Knowledge documents for AI and policy context"},
            {"name": "deals", "description": "Sponsoring/deal intake and draft tracking"},
            {"name": "audit", "description": "System and domain event audit trail"},
            {"name": "dashboard", "description": "Role-aware operational dashboard metrics"},
            {
                "name": "operations",
                "description": "Central operations inbox for open approvals and todos",
            },
            {
                "name": "search",
                "description": "Cross-domain global search with grouped, ranked results",
            },
        ],
    )

    install_error_handlers(app)

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

    app.include_router(health.router, tags=["health"])

    app.include_router(auth.router, prefix=f"{API_BASE_PREFIX}/auth", tags=["auth"])
    app.include_router(products.router, prefix=f"{API_BASE_PREFIX}/products", tags=["products"])
    app.include_router(assets.router, prefix=f"{API_BASE_PREFIX}/assets", tags=["assets"])
    app.include_router(content.router, prefix=f"{API_BASE_PREFIX}/content", tags=["content"])
    app.include_router(email.router, prefix=f"{API_BASE_PREFIX}/email", tags=["email"])
    app.include_router(images.router, prefix=f"{API_BASE_PREFIX}/images", tags=["images"])
    app.include_router(knowledge.router, prefix=f"{API_BASE_PREFIX}/knowledge", tags=["knowledge"])
    app.include_router(deals.router, prefix=f"{API_BASE_PREFIX}/deals", tags=["deals"])
    app.include_router(audit.router, prefix=f"{API_BASE_PREFIX}/audit", tags=["audit"])
    app.include_router(
        dashboard.router,
        prefix=f"{API_BASE_PREFIX}/dashboard",
        tags=["dashboard"],
    )
    app.include_router(
        operations.router,
        prefix=f"{API_BASE_PREFIX}/operations",
        tags=["operations"],
    )
    app.include_router(search.router, prefix=f"{API_BASE_PREFIX}/search", tags=["search"])

    app.include_router(
        auth.router, prefix=f"{LEGACY_API_PREFIX}/auth", tags=["auth"], deprecated=True
    )
    app.include_router(
        products.router,
        prefix=f"{LEGACY_API_PREFIX}/products",
        tags=["products"],
        deprecated=True,
    )
    app.include_router(
        assets.router, prefix=f"{LEGACY_API_PREFIX}/assets", tags=["assets"], deprecated=True
    )
    app.include_router(
        content.router, prefix=f"{LEGACY_API_PREFIX}/content", tags=["content"], deprecated=True
    )
    app.include_router(
        email.router, prefix=f"{LEGACY_API_PREFIX}/email", tags=["email"], deprecated=True
    )
    app.include_router(
        images.router, prefix=f"{LEGACY_API_PREFIX}/images", tags=["images"], deprecated=True
    )
    app.include_router(
        knowledge.router,
        prefix=f"{LEGACY_API_PREFIX}/knowledge",
        tags=["knowledge"],
        deprecated=True,
    )
    app.include_router(
        deals.router, prefix=f"{LEGACY_API_PREFIX}/deals", tags=["deals"], deprecated=True
    )
    app.include_router(
        audit.router, prefix=f"{LEGACY_API_PREFIX}/audit", tags=["audit"], deprecated=True
    )
    app.include_router(
        dashboard.router,
        prefix=f"{LEGACY_API_PREFIX}/dashboard",
        tags=["dashboard"],
        deprecated=True,
    )
    app.include_router(
        operations.router,
        prefix=f"{LEGACY_API_PREFIX}/operations",
        tags=["operations"],
        deprecated=True,
    )
    app.include_router(
        search.router,
        prefix=f"{LEGACY_API_PREFIX}/search",
        tags=["search"],
        deprecated=True,
    )

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
