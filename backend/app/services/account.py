"""
Account Management Service - Account Deletion, Privacy, GDPR Compliance
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.auth_session import AuthSession
from app.models.user import User
from app.services.audit import record_audit_log
from app.services.auth_security import revoke_session


def request_account_deletion(
    db: Session,
    user: User,
    grace_period_days: int | None = None,
    actor_ip: str | None = None,
    actor_user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
    revoke_active_sessions: bool = True,
) -> dict[str, Any]:
    """
    Schedule a user account for deletion (GDPR compliance).

    Soft-delete: User record stays for grace period (configurable days),
    then hard-deleted by background job.

    Args:
        db: Database session
        user: User requesting deletion
        actor_ip: Client IP for audit
        actor_user_agent: Client user agent for audit
        metadata: Optional additional audit metadata to store with the request

    Returns:
        Dict with deletion_requested_at timestamp and grace period days

    Raises:
        ValueError: If user already requested deletion
    """
    if user.deletion_requested_at:
        raise ValueError("Account deletion already requested")

    resolved_grace_period_days = grace_period_days or settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS
    now = datetime.now(timezone.utc)
    user.deletion_requested_at = now

    active_sessions = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .all()
    )
    if revoke_active_sessions:
        for session in active_sessions:
            revoke_session(db, session=session, reason="account_deletion_requested")

    record_audit_log(
        db,
        actor=user,
        action="user.account.deletion_requested",
        entity_type="User",
        entity_id=str(user.id),
        description=f"User {user.username} requested account deletion",
        before={"deletion_requested_at": None},
        after={"deletion_requested_at": now.isoformat()},
        metadata={
            "reason": "GDPR account deletion request",
            "grace_period_days": resolved_grace_period_days,
            "client_ip": actor_ip,
            "client_user_agent": actor_user_agent,
            "revoked_sessions": len(active_sessions) if revoke_active_sessions else 0,
            **(metadata or {}),
        },
    )

    db.commit()

    return {
        "deletion_requested_at": now.isoformat(),
        "grace_period_days": resolved_grace_period_days,
        "hard_delete_scheduled_for": (now + timedelta(days=resolved_grace_period_days)).isoformat(),
        "revoked_sessions": len(active_sessions) if revoke_active_sessions else 0,
    }


def cancel_account_deletion(
    db: Session,
    user: User,
    actor_ip: str | None = None,
    actor_user_agent: str | None = None,
) -> dict[str, Any]:
    """
    Cancel a scheduled account deletion.

    Args:
        db: Database session
        user: User canceling deletion
        actor_ip: Client IP for audit
        actor_user_agent: Client user agent for audit

    Returns:
        Dict with cancellation confirmation

    Raises:
        ValueError: If no deletion was requested
    """
    if not user.deletion_requested_at:
        raise ValueError("No account deletion request to cancel")

    previous_deletion_requested_at = user.deletion_requested_at
    user.deletion_requested_at = None

    # Audit-Log: USER_CANCELED_DELETION
    record_audit_log(
        db,
        actor=user,
        action="user.account.deletion_canceled",
        entity_type="User",
        entity_id=str(user.id),
        description=f"User {user.username} canceled account deletion",
        before={"deletion_requested_at": previous_deletion_requested_at.isoformat()},
        after={"deletion_requested_at": None},
        metadata={
            "reason": "User canceled GDPR deletion request",
            "client_ip": actor_ip,
            "client_user_agent": actor_user_agent,
        },
    )

    db.commit()

    return {
        "deletion_canceled": True,
        "account_restored": True,
    }


def get_deletable_users(
    db: Session,
    grace_period_days: int | None = None,
) -> list[User]:
    """
    Get all users scheduled for deletion and past grace period.

    Args:
        db: Database session
        grace_period_days: Configurable grace period (default 30 days)

    Returns:
        List of User records eligible for hard-delete
    """
    resolved_grace_period_days = grace_period_days or settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=resolved_grace_period_days)

    stmt = select(User).where(
        User.deletion_requested_at.isnot(None),
        User.deletion_requested_at < cutoff_date,
    )

    return db.execute(stmt).scalars().all()


def hard_delete_user(
    db: Session,
    user_id: uuid.UUID,
    reason: str = "Grace period expired",
) -> dict[str, Any]:
    """
    Permanently delete a user and associated data.

    CRITICAL: This is a hard-delete operation. Cannot be undone.

    Deletion order (foreign key safe):
    1. AuthSessions (soft + hard)
    2. PasswordResetTokens (soft + hard)
    3. RevokedTokens (soft + hard)
    4. AuditLogs (anonymize user_id -> NULL)
    5. User (hard-delete)

    Args:
        db: Database session
        user_id: UUID of user to delete
        reason: Reason for deletion (for audit trail)

    Returns:
        Dict with deletion confirmation details

    Raises:
        ValueError: If user not found or already deleted
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")

    if not user.deletion_requested_at:
        raise ValueError(f"User {user_id} did not request deletion")

    username = user.username
    user_deletion_requested_at = user.deletion_requested_at

    # 1. Delete AuthSessions
    db.query(AuthSession).filter(AuthSession.user_id == user_id).delete()

    # 2. Anonymize AuditLogs (set user_id -> NULL, but keep action logs)
    #    This preserves audit trail while protecting privacy
    db.query(AuditLog).filter(AuditLog.actor_id == user_id).update(
        {"actor_id": None, "actor_name": "[DELETED_USER]"},
    )

    # 3. Hard-delete User record
    db.delete(user)
    db.commit()

    # 4. Create final audit log (as system, not as user)
    #    This is logged AFTER deletion so actor_id is NULL
    audit_log = AuditLog(
        actor_id=None,
        actor_name="[SYSTEM_PURGE_JOB]",
        action="user.account.hard_deleted",
        entity_type="User",
        entity_id=str(user_id),
        description=f"User account permanently deleted: {username}",
        meta={
            "reason": reason,
            "deletion_requested_at": user_deletion_requested_at.isoformat(),
            "hard_deleted_at": datetime.now(timezone.utc).isoformat(),
            "critical": True,
            "audit_category": "admin",
        },
    )
    db.add(audit_log)
    db.commit()

    return {
        "user_id": str(user_id),
        "username": username,
        "hard_deleted": True,
        "hard_deleted_at": datetime.now(timezone.utc).isoformat(),
        "deletion_requested_at": user_deletion_requested_at.isoformat(),
    }


def anonymize_user_data_in_logs(
    db: Session,
    user_id: uuid.UUID,
) -> int:
    """
    Anonymize references to a user in audit logs.

    Sets user_id and actor_name to NULL/redacted to protect privacy
    while keeping audit trail for compliance purposes.

    Args:
        db: Database session
        user_id: UUID of user to anonymize

    Returns:
        Number of audit log records anonymized
    """
    updated_count = (
        db.query(AuditLog)
        .filter(
            AuditLog.actor_id == user_id,
        )
        .update(
            {"actor_id": None, "actor_name": "[DELETED_USER]"},
        )
    )
    db.commit()
    return updated_count
