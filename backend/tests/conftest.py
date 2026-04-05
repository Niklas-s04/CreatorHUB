from __future__ import annotations

import os
import sys
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test_secret_please_change_1234567890")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "test-bootstrap-admin-pass")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://creator:creator@localhost:5432/creator_suite_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/9")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("AUTH_COOKIE_SECURE", "false")
os.environ.setdefault("BOOTSTRAP_INSTALL_TOKEN", "test-bootstrap-token")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("AUTO_ARCHIVE_ENABLED", "false")
os.environ.setdefault("SECURITY_SENSITIVE_ACTION_CONFIRMATION_REQUIRED", "false")
os.environ.setdefault("SECURITY_SENSITIVE_ACTION_REQUIRE_STEP_UP_MFA", "false")

from app.api import deps
from app.api.routers import (
    assets,
    audit,
    auth,
    content,
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
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.models.asset import Asset
from app.models.audit import AuditLog
from app.models.auth_session import AuthSession, LoginHistory, PasswordResetToken, RevokedToken
from app.models.product import Product
from app.models.registration_request import RegistrationRequest
from app.models.user import User

TEST_TABLES = [
    User.__table__,
    AuthSession.__table__,
    RevokedToken.__table__,
    LoginHistory.__table__,
    PasswordResetToken.__table__,
    RegistrationRequest.__table__,
    Product.__table__,
    Asset.__table__,
    AuditLog.__table__,
]


@pytest.fixture(autouse=True)
def disable_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import auth_security

    monkeypatch.setattr(auth_security, "_get_redis", lambda: None)


@pytest.fixture(autouse=True)
def normalize_now_for_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import deps as deps_module
    from app.api.routers import auth as auth_router
    from app.services import auth_security

    monkeypatch.setattr(deps_module, "_utcnow", lambda: datetime.utcnow())
    monkeypatch.setattr(auth_router, "_utcnow", lambda: datetime.utcnow())
    monkeypatch.setattr(auth_security, "utcnow", lambda: datetime.utcnow())


@pytest.fixture(autouse=True)
def temp_storage_dirs(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(settings, "EXPORTS_DIR", str(tmp_path / "exports"))


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()


@pytest.fixture()
def app(db_session: Session) -> FastAPI:
    api = FastAPI()
    trusted_hosts = [host.strip() for host in settings.TRUSTED_HOSTS.split(",") if host.strip()]
    if trusted_hosts:
        api.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
    api.add_middleware(RequestSizeLimitMiddleware, max_body_size=settings.MAX_REQUEST_BODY_BYTES)
    api.add_middleware(
        CsrfProtectionMiddleware,
        auth_cookie_name=settings.AUTH_ACCESS_COOKIE_NAME,
        csrf_cookie_name=settings.CSRF_COOKIE_NAME,
    )
    api.add_middleware(
        SecurityHeadersMiddleware,
        hsts_seconds=settings.SECURITY_HSTS_SECONDS,
        trust_proxy_headers=settings.TRUST_PROXY_HEADERS,
        env=settings.ENV,
    )
    origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
    if origins:
        api.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    api.include_router(health.router, tags=["health"])
    api.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    api.include_router(auth.user_router, prefix="/api/v1", tags=["auth"])
    api.include_router(products.router, prefix="/api/v1/products", tags=["products"])
    api.include_router(assets.router, prefix="/api/v1/assets", tags=["assets"])
    api.include_router(content.router, prefix="/api/v1/content", tags=["content"])
    api.include_router(email.router, prefix="/api/v1/email", tags=["email"])
    api.include_router(images.router, prefix="/api/v1/images", tags=["images"])
    api.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
    api.include_router(deals.router, prefix="/api/v1/deals", tags=["deals"])
    api.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
    api.include_router(operations.router, prefix="/api/v1/operations", tags=["operations"])
    api.include_router(search.router, prefix="/api/v1/search", tags=["search"])

    api.include_router(auth.router, prefix="/api/auth", tags=["auth"], deprecated=True)
    api.include_router(auth.user_router, prefix="/api", tags=["auth"], deprecated=True)
    api.include_router(products.router, prefix="/api/products", tags=["products"], deprecated=True)
    api.include_router(assets.router, prefix="/api/assets", tags=["assets"], deprecated=True)
    api.include_router(content.router, prefix="/api/content", tags=["content"], deprecated=True)
    api.include_router(email.router, prefix="/api/email", tags=["email"], deprecated=True)
    api.include_router(images.router, prefix="/api/images", tags=["images"], deprecated=True)
    api.include_router(
        knowledge.router, prefix="/api/knowledge", tags=["knowledge"], deprecated=True
    )
    api.include_router(deals.router, prefix="/api/deals", tags=["deals"], deprecated=True)
    api.include_router(audit.router, prefix="/api/audit", tags=["audit"], deprecated=True)
    api.include_router(
        operations.router, prefix="/api/operations", tags=["operations"], deprecated=True
    )
    api.include_router(search.router, prefix="/api/search", tags=["search"], deprecated=True)

    def _get_db_override() -> Generator[Session, None, None]:
        yield db_session

    api.dependency_overrides[deps.get_db] = _get_db_override
    return api


@pytest.fixture()
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
