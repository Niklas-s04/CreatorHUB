"""
Background job to permanently purge users who requested deletion 30+ days ago.

Also anonymizes their audit logs for privacy compliance.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.auth_session import AuthSession, RevokedToken
from app.models.user import User
from app.services.audit import record_audit_log

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def purge_deleted_users(
    grace_period_days: int | None = None,
    db: Session | None = None,
) -> dict[str, int]:
    """
    Permanently delete users who requested deletion more than grace_period_days ago.

    Returns statistics about the purge operation.
    """
    own_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        stats = {
            "users_purged": 0,
            "sessions_deleted": 0,
            "tokens_revoked": 0,
            "audit_logs_anonymized": 0,
            "errors": 0,
        }

        resolved_grace_period_days = (
            grace_period_days or settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS
        )

        # Calculate cutoff date: now - grace_period_days
        cutoff_date = _utcnow() - timedelta(days=resolved_grace_period_days)

        # Find users scheduled for deletion and past grace period.
        users_to_purge = (
            db.execute(
                select(User).where(
                    and_(
                        User.deletion_requested_at.isnot(None),
                        User.deletion_requested_at < cutoff_date,
                    )
                )
            )
            .scalars()
            .all()
        )

        for user in users_to_purge:
            try:
                user_id = user.id

                # Delete all auth sessions for this user and collect their token JTIs
                sessions = db.query(AuthSession).filter(AuthSession.user_id == user_id).all()
                revoked_jtis: set[str] = set()
                for session in sessions:
                    if session.refresh_jti:
                        revoked_jtis.add(session.refresh_jti)
                    if session.last_access_jti:
                        revoked_jtis.add(session.last_access_jti)
                    db.delete(session)
                stats["sessions_deleted"] += len(sessions)

                # Remove revoked tokens that belong to the deleted sessions
                revoked_tokens = []
                if revoked_jtis:
                    revoked_tokens = (
                        db.query(RevokedToken)
                        .filter(RevokedToken.jti.in_(list(revoked_jtis)))
                        .all()
                    )
                for token in revoked_tokens:
                    db.delete(token)
                stats["tokens_revoked"] += len(revoked_tokens)

                # Anonymize audit logs: set user_id to None, keep action but remove personally identifying details
                affected_logs = db.query(AuditLog).filter(AuditLog.actor_id == user_id).all()
                for audit_log in affected_logs:
                    audit_log.actor_id = None
                    audit_log.actor_name = f"[deleted-user-{user_id}]"
                    audit_log.description = "[User data anonymized during account deletion purge]"
                    audit_log.before = None
                    audit_log.after = None
                    # Keep action and basic tracking for compliance
                stats["audit_logs_anonymized"] += len(affected_logs)

                # Hard-delete the user
                db.delete(user)
                stats["users_purged"] += 1
                record_audit_log(
                    db=db,
                    actor=None,
                    actor_label="system:purge-deleted-users",
                    action="auth.user.permanently_deleted",
                    entity_type="User",
                    entity_id=str(user_id),
                    description="User permanently deleted after account deletion grace period.",
                    metadata={
                        "event_code": "USER_PERMANENTLY_DELETED",
                        "deletion_requested_at": user.deletion_requested_at.isoformat()
                        if user.deletion_requested_at
                        else None,
                    },
                )

                # Commit this user's deletion atomically
                db.commit()

            except Exception:
                db.rollback()
                stats["errors"] += 1
                logger.exception("Error purging user %s", user_id)
                continue

        # Create summary audit log for compliance
        if stats["users_purged"] > 0:
            try:
                record_audit_log(
                    db=db,
                    actor=None,
                    actor_label="system:purge-deleted-users",
                    action="auth.user.purged",
                    entity_type="User",
                    entity_id=None,
                    description=f"Batch purge of deleted users completed. Purged {stats['users_purged']} user(s) after {grace_period_days}-day retention period.",
                    metadata={
                        "users_purged": stats["users_purged"],
                        "sessions_deleted": stats["sessions_deleted"],
                        "tokens_revoked": stats["tokens_revoked"],
                        "audit_logs_anonymized": stats["audit_logs_anonymized"],
                        "grace_period_days": resolved_grace_period_days,
                    },
                )
                db.commit()
            except Exception:
                logger.exception("Error creating deleted-user purge summary audit log")
                db.rollback()

        return stats

    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    # Standalone execution for testing or manual runs
    result = purge_deleted_users()
    print("Purge Results:")
    for key, value in result.items():
        print(f"  {key}: {value}")
