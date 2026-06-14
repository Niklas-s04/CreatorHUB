from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.asset import Asset, AssetKind, AssetOwnerType, AssetReviewState, AssetSource
from app.models.audit import AuditLog
from app.models.content import ContentItem, ContentTask, TaskStatus, TaskType
from app.models.deal import DealDraft, DealDraftStatus
from app.models.email import EmailDraft, EmailThread
from app.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from app.models.user import UserRole
from tests.factories import create_user, login


def test_dashboard_summary_returns_role_aware_metrics(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, username="admin", role=UserRole.admin)
    login(client, username="admin")

    deal = DealDraft(status=DealDraftStatus.review, brand_name="Brand")
    asset = Asset(
        owner_type=AssetOwnerType.product,
        owner_id=uuid.uuid4(),
        kind=AssetKind.image,
        source=AssetSource.upload,
        review_state=AssetReviewState.pending_review,
        title="Asset",
    )
    content_item = ContentItem(title="Content")
    task = ContentTask(
        content_item=content_item,
        type=TaskType.edit,
        status=TaskStatus.todo,
        due_date=date.today() - timedelta(days=1),
    )
    thread = EmailThread(subject="Thread", raw_body="Hello")
    draft = EmailDraft(
        thread=thread,
        draft_subject="Draft",
        draft_body="Body",
        risk_flags='["missing_terms"]',
    )
    registration = RegistrationRequest(
        username="pending-user",
        hashed_password=hash_password("VeryStrong!Pass123"),
        status=RegistrationRequestStatus.pending,
    )
    audit = AuditLog(action="login_failed", entity_type="auth")
    db_session.add_all([deal, asset, content_item, task, thread, draft, registration, audit])
    db_session.commit()

    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    metrics = {metric["key"]: metric for metric in body["metrics"]}
    assert metrics["open_deals"]["count"] == 1
    assert metrics["unreviewed_assets"]["count"] == 1
    assert metrics["overdue_tasks"]["count"] == 1
    assert metrics["risky_email_drafts"]["count"] == 1
    assert metrics["pending_registration_requests"]["count"] == 1
    assert metrics["audit_incidents"]["count"] == 1


def test_dashboard_summary_limits_metrics_to_viewer_permissions(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, username="viewer", role=UserRole.viewer)
    login(client, username="viewer")

    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "viewer"
    assert {metric["key"] for metric in body["metrics"]} == {
        "open_deals",
        "overdue_tasks",
        "risky_email_drafts",
    }
