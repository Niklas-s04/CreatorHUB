from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.auth_session import AuthSession, RevokedToken
from app.models.user import User
from app.workers.tasks.purge_deleted_users import purge_deleted_users
from tests.factories import create_user


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def test_purge_deleted_users_removes_expired_user_data(db_session: Session) -> None:
    user = create_user(db_session, username="purge_me")
    user.is_active = False
    user.deletion_requested_at = _utcnow() - timedelta(days=31)
    db_session.commit()

    session = AuthSession(
        user_id=user.id,
        refresh_token_hash="hash",
        refresh_jti="refresh-jti",
        last_access_jti="access-jti",
        idle_expires_at=_utcnow() + timedelta(days=1),
        expires_at=_utcnow() + timedelta(days=1),
    )
    revoked = RevokedToken(jti="refresh-jti", expires_at=_utcnow() + timedelta(days=1))
    audit_log = AuditLog(
        actor_id=user.id, actor_name=user.username, action="test", entity_type="User"
    )
    db_session.add_all([session, revoked, audit_log])
    db_session.commit()

    stats = purge_deleted_users(grace_period_days=30, db=db_session)

    assert stats["users_purged"] == 1
    assert db_session.query(User).filter(User.id == user.id).count() == 0
    assert db_session.query(AuthSession).filter(AuthSession.user_id == user.id).count() == 0
    assert db_session.query(RevokedToken).count() == 0
    anonymized = (
        db_session.query(AuditLog).filter(AuditLog.actor_name.like("[deleted-user-%")).first()
    )
    assert anonymized is not None


def test_purge_deleted_users_daemon_uses_configured_interval(monkeypatch) -> None:
    from app.core.config import settings
    from app.services import purge_deleted_users_daemon as daemon

    calls: list[object] = []
    monkeypatch.setattr(settings, "PURGE_DELETED_USERS_INTERVAL_HOURS", 2)
    monkeypatch.setattr(
        daemon,
        "purge_deleted_users",
        lambda grace_period_days: calls.append(grace_period_days) or {"users_purged": 0},
    )

    async def fake_sleep(seconds: float) -> None:
        calls.append(seconds)
        if calls.count(seconds) >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(daemon.asyncio, "sleep", fake_sleep)

    asyncio.run(daemon.purge_deleted_users_daemon())

    assert 7200 in calls
    assert settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS in calls
