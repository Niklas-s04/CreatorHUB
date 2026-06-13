from __future__ import annotations

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
