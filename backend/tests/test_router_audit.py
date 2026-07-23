from __future__ import annotations

import enum
import json
import uuid
from collections.abc import Generator
from datetime import date, datetime, time, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api.routers import audit
from app.models.audit import AuditLog
from app.models.user import User
from app.services.audit import _normalize, record_audit_log
from tests.factories import create_user

TEST_TABLES = [
    User.__table__,
    AuditLog.__table__,
]


def _build_app(db_session: Session, current_user: User) -> FastAPI:
    app = FastAPI()
    app.include_router(audit.router, prefix="/api/audit")

    def _get_db_override() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[deps.get_db] = _get_db_override
    app.dependency_overrides[deps.get_current_user] = lambda: current_user
    return app


def test_audit_list_filters_category_and_critical() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = session_local()

    try:
        admin = create_user(db, username="audit_admin")
        record_audit_log(
            db,
            actor=admin,
            action="auth.password.change",
            entity_type="user",
            entity_id=str(admin.id),
            metadata={"audit_category": "security", "critical": True},
        )
        record_audit_log(
            db,
            actor=admin,
            action="content.task.update",
            entity_type="content_task",
            entity_id="ct-1",
            metadata={"audit_category": "domain", "critical": False},
        )
        db.commit()

        app = _build_app(db, admin)
        with TestClient(app) as client:
            response = client.get("/api/audit/?category=security&critical_only=true")

        assert response.status_code == 200
        body = response.json()
        assert body["meta"]["total"] == 1
        assert body["items"][0]["action"] == "auth.password.change"
    finally:
        db.close()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()


def test_audit_export_csv_respects_filters() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = session_local()

    try:
        admin = create_user(db, username="audit_export_admin")
        record_audit_log(
            db,
            actor=admin,
            action="registration.request.review",
            entity_type="registration_request",
            entity_id="req-1",
            metadata={"audit_category": "approval", "critical": True},
        )
        record_audit_log(
            db,
            actor=admin,
            action="email.draft.update",
            entity_type="email_draft",
            entity_id="draft-1",
            metadata={"audit_category": "ai_action", "critical": False},
        )
        db.commit()

        app = _build_app(db, admin)
        with TestClient(app) as client:
            response = client.get("/api/audit/export/csv?category=approval")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "registration.request.review" in response.text
        assert "email.draft.update" not in response.text
    finally:
        db.close()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()


def test_audit_log_redacts_sensitive_fields() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = session_local()

    try:
        admin = create_user(db, username="audit_redact_admin")
        log = record_audit_log(
            db,
            actor=admin,
            action="auth.password.change",
            entity_type="user",
            entity_id=str(admin.id),
            before={
                "password": "secret-value",
                "nested": {"token": "abc"},
                "changed_at": datetime(2026, 7, 23, 12, 30, tzinfo=timezone.utc),
                "amount": Decimal("19.9900"),
            },
            after={"profile": {"mfa_secret": "totp-secret"}},
            metadata={
                "refresh_token": "refresh-value",
                "note": "safe",
                "event_id": uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
            },
        )
        db.commit()

        assert log.before == {
            "password": "***REDACTED***",
            "nested": {"token": "***REDACTED***"},
            "changed_at": "2026-07-23T12:30:00+00:00",
            "amount": "19.9900",
        }
        assert log.after == {"profile": {"mfa_secret": "***REDACTED***"}}
        assert log.meta["refresh_token"] == "***REDACTED***"
        assert log.meta["note"] == "safe"
        assert log.meta["event_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    finally:
        db.close()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()


def test_audit_normalize_makes_complex_values_and_dict_keys_json_safe() -> None:
    class AuditValue(enum.Enum):
        approved = "approved"

    key = uuid.uuid4()
    normalized = _normalize(
        {
            key: {
                AuditValue.approved: (
                    date(2026, 7, 23),
                    datetime(2026, 7, 23, 12, 30, tzinfo=timezone.utc),
                    time(12, 30, 45),
                    Decimal("1234.5600"),
                    uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
                ),
                "sequence": range(3),
            }
        }
    )

    assert json.loads(json.dumps(normalized)) == {
        str(key): {
            "approved": [
                "2026-07-23",
                "2026-07-23T12:30:00+00:00",
                "12:30:45",
                "1234.5600",
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            ],
            "sequence": [0, 1, 2],
        }
    }
