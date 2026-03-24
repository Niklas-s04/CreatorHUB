from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.authorization import Permission, has_permission
from app.models.asset import Asset, AssetReviewState
from app.models.audit import AuditLog
from app.models.content import ContentTask, TaskStatus
from app.models.deal import DealDraft, DealDraftStatus
from app.models.email import EmailDraft
from app.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from app.models.user import User
from app.schemas.dashboard import DashboardListItem, DashboardMetric, DashboardSummaryOut

router = APIRouter()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _risk_flag_count(raw_flags: str | None) -> int:
    if not raw_flags:
        return 0
    try:
        parsed = json.loads(raw_flags)
        if isinstance(parsed, list):
            return len(parsed)
    except (TypeError, ValueError):
        return 0
    return 0


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardSummaryOut:
    metrics: list[DashboardMetric] = []

    if has_permission(current_user, Permission.deal_read) or has_permission(
        current_user, Permission.deal_manage
    ):
        open_statuses = [
            DealDraftStatus.intake,
            DealDraftStatus.review,
            DealDraftStatus.negotiating,
        ]
        deals_query = db.query(DealDraft).filter(DealDraft.status.in_(open_statuses))
        deals_items = deals_query.order_by(DealDraft.updated_at.desc()).limit(5).all()
        metrics.append(
            DashboardMetric(
                key="open_deals",
                label="Offene Deals",
                description="Deal-Drafts in Intake, Review oder Negotiating.",
                count=deals_query.order_by(None).count(),
                route="/email",
                tone="warn",
                items=[
                    DashboardListItem(
                        id=str(deal.id),
                        title=deal.brand_name or deal.contact_name or "Deal ohne Namen",
                        subtitle=f"Status: {deal.status.value}",
                        updated_at=deal.updated_at,
                    )
                    for deal in deals_items
                ],
            )
        )

    if has_permission(current_user, Permission.asset_review):
        review_states = [
            AssetReviewState.quarantine,
            AssetReviewState.pending_review,
            AssetReviewState.needs_review,
            AssetReviewState.pending,
        ]
        assets_query = db.query(Asset).filter(Asset.review_state.in_(review_states))
        assets_items = assets_query.order_by(Asset.updated_at.desc()).limit(5).all()
        metrics.append(
            DashboardMetric(
                key="unreviewed_assets",
                label="Ungeprüfte Assets",
                description="Assets in Quarantäne/Pending-Review ohne finalen Freigabestatus.",
                count=assets_query.order_by(None).count(),
                route="/assets",
                tone="warn",
                items=[
                    DashboardListItem(
                        id=str(asset.id),
                        title=asset.title or "Asset ohne Titel",
                        subtitle=f"{asset.owner_type.value} · {asset.review_state.value}",
                        updated_at=asset.updated_at,
                    )
                    for asset in assets_items
                ],
            )
        )

    if has_permission(current_user, Permission.content_read) or has_permission(
        current_user, Permission.content_manage
    ):
        today = date.today()
        tasks_query = db.query(ContentTask).filter(
            and_(
                ContentTask.status != TaskStatus.done,
                ContentTask.due_date.isnot(None),
                ContentTask.due_date < today,
            )
        )
        tasks_items = tasks_query.order_by(ContentTask.due_date.asc()).limit(5).all()
        metrics.append(
            DashboardMetric(
                key="overdue_tasks",
                label="Überfällige Aufgaben",
                description="Offene Content-Tasks mit überschrittenem Fälligkeitsdatum.",
                count=tasks_query.order_by(None).count(),
                route="/content",
                tone="danger",
                items=[
                    DashboardListItem(
                        id=str(task.id),
                        title=f"Task {task.type.value}",
                        subtitle=f"Status: {task.status.value}",
                        updated_at=task.due_date,
                    )
                    for task in tasks_items
                ],
            )
        )

    if has_permission(current_user, Permission.email_read) or has_permission(
        current_user, Permission.email_generate
    ):
        drafts_query = db.query(EmailDraft).filter(
            and_(
                EmailDraft.risk_flags.isnot(None),
                EmailDraft.risk_flags != "",
                EmailDraft.risk_flags != "[]",
            )
        )
        drafts_items = drafts_query.order_by(EmailDraft.updated_at.desc()).limit(5).all()
        metrics.append(
            DashboardMetric(
                key="risky_email_drafts",
                label="Riskante E-Mail-Entwürfe",
                description="Entwürfe mit gesetzten Risk-Flags.",
                count=drafts_query.order_by(None).count(),
                route="/email",
                tone="danger",
                items=[
                    DashboardListItem(
                        id=str(draft.id),
                        title=draft.draft_subject or "Entwurf ohne Betreff",
                        subtitle=f"Risiko-Flags: {_risk_flag_count(draft.risk_flags)}",
                        updated_at=draft.updated_at,
                    )
                    for draft in drafts_items
                ],
            )
        )

    if has_permission(current_user, Permission.user_approve_registration):
        registration_query = db.query(RegistrationRequest).filter(
            RegistrationRequest.status == RegistrationRequestStatus.pending
        )
        registration_items = (
            registration_query.order_by(RegistrationRequest.created_at.desc()).limit(5).all()
        )
        metrics.append(
            DashboardMetric(
                key="pending_registration_requests",
                label="Offene Registrierungsfreigaben",
                description="Registrierungsanfragen im Status Pending.",
                count=registration_query.order_by(None).count(),
                route="/admin",
                tone="warn",
                items=[
                    DashboardListItem(
                        id=str(req.id),
                        title=req.username,
                        subtitle="Wartet auf Freigabe",
                        updated_at=req.created_at,
                    )
                    for req in registration_items
                ],
            )
        )

    if has_permission(current_user, Permission.audit_view):
        incident_since = _now_utc() - timedelta(days=7)
        audit_query = db.query(AuditLog).filter(AuditLog.created_at >= incident_since)
        audit_items = audit_query.order_by(AuditLog.created_at.desc()).limit(5).all()
        metrics.append(
            DashboardMetric(
                key="audit_incidents",
                label="Audit-relevante Vorfälle",
                description="Audit-Events der letzten 7 Tage.",
                count=audit_query.order_by(None).count(),
                route="/audit",
                tone="info",
                items=[
                    DashboardListItem(
                        id=str(entry.id),
                        title=entry.action,
                        subtitle=entry.description or entry.entity_type,
                        updated_at=entry.created_at,
                    )
                    for entry in audit_items
                ],
            )
        )

    return DashboardSummaryOut(
        generated_at=_now_utc(),
        role=current_user.role.value,
        metrics=metrics,
    )
