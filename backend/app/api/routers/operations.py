from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.authorization import Permission, has_permission
from app.models.asset import Asset, AssetOwnerType, AssetReviewState
from app.models.content import ContentItem, ContentTask, TaskPriority, TaskStatus
from app.models.deal import DealDraft, DealDraftStatus
from app.models.email import EmailDraft
from app.models.product import Product
from app.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from app.models.user import User, UserRole
from app.schemas.operations import (
    OperationDueFilter,
    OperationInboxItem,
    OperationInboxOut,
    OperationPriority,
)
from app.services.deal_checklists import missing_required_items

router = APIRouter()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_aware_datetime(value: datetime | date | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)


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


def _apply_filters(
    items: list[OperationInboxItem],
    *,
    assignee_user: str | None,
    role: UserRole | None,
    priority: OperationPriority | None,
    due: OperationDueFilter,
) -> list[OperationInboxItem]:
    now = _now_utc()
    today = now.date()

    filtered: list[OperationInboxItem] = []
    assignee_norm = assignee_user.strip().lower() if assignee_user else None

    for item in items:
        if assignee_norm:
            candidate = (item.assignee_username or "unassigned").strip().lower()
            if candidate != assignee_norm:
                continue

        if role and item.responsible_role != role.value:
            continue

        if priority and item.priority != priority:
            continue

        due_at = _to_aware_datetime(item.due_at)
        if due == "overdue":
            if not due_at or due_at.date() >= today:
                continue
        elif due == "today":
            if not due_at or due_at.date() != today:
                continue
        elif due == "next7":
            if not due_at:
                continue
            due_date = due_at.date()
            if due_date < today or due_date > (today + timedelta(days=7)):
                continue
        elif due == "none":
            if due_at is not None:
                continue

        filtered.append(item)

    return filtered


@router.get("/inbox", response_model=OperationInboxOut)
def operations_inbox(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    assignee_user: str | None = Query(default=None),
    role: UserRole | None = Query(default=None),
    priority: OperationPriority | None = Query(default=None),
    due: OperationDueFilter = Query(default="all"),
    limit: int = Query(default=200, ge=1, le=500),
) -> OperationInboxOut:
    now = _now_utc()
    items: list[OperationInboxItem] = []

    if has_permission(current_user, Permission.asset_review):
        states = [
            AssetReviewState.quarantine,
            AssetReviewState.pending_review,
            AssetReviewState.needs_review,
            AssetReviewState.pending,
        ]
        assets = (
            db.query(Asset)
            .filter(Asset.review_state.in_(states))
            .order_by(Asset.updated_at.desc())
            .limit(limit)
            .all()
        )
        for asset in assets:
            due_at = asset.created_at + timedelta(days=2) if asset.created_at else None
            is_old = bool(
                asset.created_at and (now - _to_aware_datetime(asset.created_at)).days >= 3
            )
            priority_value: OperationPriority = (
                "critical"
                if asset.review_state == AssetReviewState.quarantine
                else ("high" if is_old else "medium")
            )
            items.append(
                OperationInboxItem(
                    id=f"asset:{asset.id}",
                    kind="asset_review",
                    title=asset.title or "Asset ohne Titel",
                    description=f"Review erforderlich ({asset.review_state.value})",
                    source_route="/assets",
                    source_id=str(asset.id),
                    priority=priority_value,
                    escalation=priority_value in {"high", "critical"},
                    due_at=due_at,
                    created_at=asset.created_at,
                    updated_at=asset.updated_at,
                    assignee_username=None,
                    responsible_role="editor",
                )
            )

    if has_permission(current_user, Permission.user_approve_registration):
        requests = (
            db.query(RegistrationRequest)
            .filter(RegistrationRequest.status == RegistrationRequestStatus.pending)
            .order_by(RegistrationRequest.created_at.asc())
            .limit(limit)
            .all()
        )
        for req in requests:
            due_at = req.created_at + timedelta(days=1) if req.created_at else None
            escalated = bool(
                req.created_at and (now - _to_aware_datetime(req.created_at)) >= timedelta(hours=48)
            )
            registration_priority: OperationPriority = "high" if escalated else "medium"
            items.append(
                OperationInboxItem(
                    id=f"registration:{req.id}",
                    kind="registration_approval",
                    title=f"Registrierung: {req.username}",
                    description="Freigabe ausstehend",
                    source_route="/admin",
                    source_id=str(req.id),
                    priority=registration_priority,
                    escalation=escalated,
                    due_at=due_at,
                    created_at=req.created_at,
                    updated_at=req.updated_at,
                    assignee_username=None,
                    responsible_role="admin",
                )
            )

    if has_permission(current_user, Permission.email_read) or has_permission(
        current_user, Permission.email_generate
    ):
        drafts = (
            db.query(EmailDraft)
            .filter(
                and_(
                    EmailDraft.approved.is_(False),
                    EmailDraft.risk_flags.isnot(None),
                    EmailDraft.risk_flags != "",
                    EmailDraft.risk_flags != "[]",
                )
            )
            .order_by(EmailDraft.updated_at.desc())
            .limit(limit)
            .all()
        )
        for draft in drafts:
            risk_count = _risk_flag_count(draft.risk_flags)
            email_priority: OperationPriority = "critical" if risk_count >= 3 else "high"
            items.append(
                OperationInboxItem(
                    id=f"email:{draft.id}",
                    kind="email_risk",
                    title=draft.draft_subject or "Riskanter E-Mail-Entwurf",
                    description=f"{risk_count} Risk-Flags",
                    source_route="/email",
                    source_id=str(draft.id),
                    priority=email_priority,
                    escalation=True,
                    due_at=draft.updated_at + timedelta(days=1) if draft.updated_at else None,
                    created_at=draft.created_at,
                    updated_at=draft.updated_at,
                    assignee_username=None,
                    responsible_role="editor",
                )
            )

    if has_permission(current_user, Permission.content_manage) or has_permission(
        current_user, Permission.content_read
    ):
        today = date.today()
        overdue_tasks = (
            db.query(ContentTask)
            .filter(
                and_(
                    ContentTask.status != TaskStatus.done,
                    ContentTask.due_date.isnot(None),
                    ContentTask.due_date < today,
                )
            )

    if has_permission(current_user, Permission.deal_manage) or has_permission(
        current_user, Permission.deal_read
    ):
        open_deals = (
            db.query(DealDraft)
            .filter(DealDraft.status.in_([DealDraftStatus.review, DealDraftStatus.negotiating]))
            .order_by(DealDraft.updated_at.desc())
            .limit(limit)
            .all()
        )
        for deal in open_deals:
            missing_items = missing_required_items(deal.checklist)
            if not missing_items:
                continue
            items.append(
                OperationInboxItem(
                    id=f"deal-checklist:{deal.id}",
                    kind="deal_checklist",
                    title=deal.brand_name or deal.contact_name or "Deal ohne Namen",
                    description=f"Pflichtpunkte offen: {', '.join(missing_items)}",
                    source_route="/deals",
                    source_id=str(deal.id),
                    priority="high",
                    escalation=True,
                    due_at=deal.updated_at + timedelta(days=1) if deal.updated_at else None,
                    created_at=deal.created_at,
                    updated_at=deal.updated_at,
                    assignee_username=None,
                    responsible_role="editor",
                )
            )

    if has_permission(current_user, Permission.product_read):
        products = db.query(Product).order_by(Product.updated_at.desc()).limit(limit).all()
        for product in products:
            approved_assets = (
                db.query(Asset)
                .filter(
                    Asset.owner_type == AssetOwnerType.product,
                    Asset.owner_id == product.id,
                    Asset.review_state == AssetReviewState.approved,
                )
                .count()
            )
            linked_content = (
                db.query(ContentItem).filter(ContentItem.product_id == product.id).count()
            )
            linked_deals = db.query(DealDraft).filter(DealDraft.product_id == product.id).count()

            if approved_assets == 0:
                items.append(
                    OperationInboxItem(
                        id=f"workflow-gap:{product.id}:asset",
                        kind="workflow_gap",
                        title=product.title,
                        description="Produkt ohne freigegebenes Asset (Medienbruch Produkt → Asset)",
                        source_route="/products",
                        source_id=str(product.id),
                        priority="high",
                        escalation=True,
                        due_at=product.updated_at + timedelta(days=2) if product.updated_at else None,
                        created_at=product.created_at,
                        updated_at=product.updated_at,
                        assignee_username=None,
                        responsible_role="editor",
                    )
                )
            elif linked_content == 0:
                items.append(
                    OperationInboxItem(
                        id=f"workflow-gap:{product.id}:content",
                        kind="workflow_gap",
                        title=product.title,
                        description="Asset vorhanden, aber kein Content geplant (Bruch Asset → Content)",
                        source_route="/content",
                        source_id=str(product.id),
                        priority="medium",
                        escalation=False,
                        due_at=product.updated_at + timedelta(days=3) if product.updated_at else None,
                        created_at=product.created_at,
                        updated_at=product.updated_at,
                        assignee_username=None,
                        responsible_role="editor",
                    )
                )
            elif linked_deals == 0:
                items.append(
                    OperationInboxItem(
                        id=f"workflow-gap:{product.id}:deal",
                        kind="workflow_gap",
                        title=product.title,
                        description="Content vorhanden, aber kein Deal/Kommunikationslink (Bruch Content → Kommunikation)",
                        source_route="/deals",
                        source_id=str(product.id),
                        priority="medium",
                        escalation=False,
                        due_at=product.updated_at + timedelta(days=4) if product.updated_at else None,
                        created_at=product.created_at,
                        updated_at=product.updated_at,
                        assignee_username=None,
                        responsible_role="editor",
                    )
                )
            .order_by(ContentTask.due_date.asc())
            .limit(limit)
            .all()
        )
        assignee_ids = [task.assignee_user_id for task in overdue_tasks if task.assignee_user_id]
        assignee_map: dict[str, str] = {}
        if assignee_ids:
            users = db.query(User).filter(User.id.in_(assignee_ids)).all()
            assignee_map = {str(user.id): user.username for user in users}
        for task in overdue_tasks:
            overdue_days = (today - task.due_date).days if task.due_date else 0
            if task.priority == TaskPriority.critical:
                content_priority: OperationPriority = "critical"
            elif task.priority == TaskPriority.high:
                content_priority = "high"
            else:
                content_priority = "critical" if overdue_days >= 7 else "high" if overdue_days >= 3 else "medium"

            assignee_username = None
            if task.assignee_user_id:
                assignee_username = assignee_map.get(str(task.assignee_user_id))
            elif task.assignee_role:
                assignee_username = f"role:{task.assignee_role.value}"

            items.append(
                OperationInboxItem(
                    id=f"content:{task.id}",
                    kind="content_overdue",
                    title=f"Überfällige Task: {task.type.value}",
                    description=(
                        f"Status {task.status.value} · Priorität {task.priority.value} · {overdue_days} Tage überfällig"
                    ),
                    source_route="/content",
                    source_id=str(task.id),
                    priority=content_priority,
                    escalation=content_priority in {"high", "critical"},
                    due_at=task.due_date,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    assignee_username=assignee_username,
                    responsible_role="editor",
                )
            )

    items.sort(
        key=lambda entry: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}[entry.priority],
            _to_aware_datetime(entry.due_at) or datetime.max.replace(tzinfo=timezone.utc),
        )
    )

    filtered_items = _apply_filters(
        items,
        assignee_user=assignee_user,
        role=role,
        priority=priority,
        due=due,
    )

    return OperationInboxOut(
        generated_at=now,
        total_open=len(filtered_items),
        items=filtered_items,
    )
