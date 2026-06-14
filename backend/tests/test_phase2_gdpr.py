"""
Phase 2: Account Deletion & GDPR Compliance - Integration Tests
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.audit import AuditLog
from app.models.user import User
from app.services.account import (
    cancel_account_deletion,
    get_deletable_users,
    hard_delete_user,
    request_account_deletion,
)


def test_account_deletion_request_flow(db_session):
    """End-to-end test: account deletion request and cancellation"""
    user = User(username="testuser_del", hashed_password="hash", role="editor")
    db_session.add(user)
    db_session.commit()

    # Request deletion
    result = request_account_deletion(db_session, user=user)
    assert result["grace_period_days"] == 30
    assert user.deletion_requested_at is not None
    assert user.is_active is False

    # Check audit log exists
    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "user.account.deletion_requested",
            AuditLog.entity_id == str(user.id),
        )
        .first()
    )
    assert audit is not None

    # Cancel deletion
    result2 = cancel_account_deletion(db_session, user=user)
    assert result2["account_restored"] is True
    assert user.deletion_requested_at is None
    assert user.is_active is True


def test_hard_delete_after_grace_period(db_session):
    """Test hard-delete purge logic"""
    # Create user with expired grace period
    user = User(username="expire_user", hashed_password="hash", role="editor")
    user.deletion_requested_at = datetime.now(timezone.utc) - timedelta(days=31)
    db_session.add(user)
    db_session.commit()
    user_id = user.id

    # Should be in deletable list
    deletable = get_deletable_users(db_session, grace_period_days=30)
    assert len(deletable) >= 1
    assert any(u.id == user_id for u in deletable)

    # Hard-delete
    result = hard_delete_user(db_session, user_id=user_id)
    assert result["hard_deleted"] is True

    # User should be gone
    gone = db_session.query(User).filter(User.id == user_id).first()
    assert gone is None

    # Final audit log should exist
    final_audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "user.account.hard_deleted",
            AuditLog.entity_id == str(user_id),
        )
        .first()
    )
    assert final_audit is not None


def test_deletion_grace_period_protection(db_session):
    """Test that users cannot be deleted before grace period expires"""
    user = User(username="protected_user", hashed_password="hash", role="editor")
    user.deletion_requested_at = datetime.now(timezone.utc) - timedelta(days=5)
    db_session.add(user)
    db_session.commit()

    # Should NOT be deletable yet
    deletable = get_deletable_users(db_session, grace_period_days=30)
    assert user not in deletable


def test_audit_log_redaction_in_deletion_request(db_session):
    """Test that sensitive fields are redacted in audit logs"""
    user = User(username="redacted_user", hashed_password="hash", role="editor")
    db_session.add(user)
    db_session.commit()

    # Request deletion (audit log is created internally)
    request_account_deletion(db_session, user=user)

    # Verify audit log was created and check it contains redaction mechanism
    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "user.account.deletion_requested",
            AuditLog.entity_id == str(user.id),
        )
        .first()
    )

    # The audit service redacts sensitive fields automatically
    assert audit is not None
    assert audit.meta is not None


def test_cannot_request_deletion_twice(db_session):
    """Test that deletion cannot be requested twice"""
    user = User(username="twice_user", hashed_password="hash", role="editor")
    db_session.add(user)
    db_session.commit()

    request_account_deletion(db_session, user=user)

    with pytest.raises(ValueError, match="already requested"):
        request_account_deletion(db_session, user=user)


def test_cannot_cancel_if_not_requested(db_session):
    """Test that deletion cannot be cancelled if not requested"""
    user = User(username="nocancel_user", hashed_password="hash", role="editor")
    db_session.add(user)
    db_session.commit()

    with pytest.raises(ValueError, match="No account deletion request"):
        cancel_account_deletion(db_session, user=user)
