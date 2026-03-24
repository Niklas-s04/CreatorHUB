from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.authorization import Permission, has_permission
from app.models.asset import Asset, AssetReviewState
from app.models.content import ContentTask, TaskStatus
from app.models.email import EmailDraft
from app.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from app.models.user import User, UserRole
from app.schemas.operations import OperationDueFilter, OperationInboxItem, OperationInboxOut, OperationPriority

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
            is_old = bool(asset.created_at and (now - _to_aware_datetime(asset.created_at)).days >= 3)
            priority_value: OperationPriority = "critical" if asset.review_state == AssetReviewState.quarantine else ("high" if is_old else "medium")
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
            escalated = bool(req.created_at and (now - _to_aware_datetime(req.created_at)) >= timedelta(hours=48))
            priority_value: OperationPriority = "high" if escalated else "medium"
            items.append(
                OperationInboxItem(
                    id=f"registration:{req.id}",
                    kind="registration_approval",
                    title=f"Registrierung: {req.username}",
                    description="Freigabe ausstehend",
                    source_route="/admin",
                    source_id=str(req.id),
                    priority=priority_value,
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
            priority_value: OperationPriority = "critical" if risk_count >= 3 else "high"
            items.append(
                OperationInboxItem(
                    id=f"email:{draft.id}",
                    kind="email_risk",
                    title=draft.draft_subject or "Riskanter E-Mail-Entwurf",
                    description=f"{risk_count} Risk-Flags",
                    source_route="/email",
                    source_id=str(draft.id),
                    priority=priority_value,
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
            .order_by(ContentTask.due_date.asc())
            .limit(limit)
            .all()
        )
        for task in overdue_tasks:
            overdue_days = (today - task.due_date).days if task.due_date else 0
            priority_value: OperationPriority = (
                "critical" if overdue_days >= 7 else "high" if overdue_days >= 3 else "medium"
            )
            items.append(
                OperationInboxItem(
                    id=f"content:{task.id}",
                    kind="content_overdue",
                    title=f"Überfällige Task: {task.type.value}",
                    description=f"Status {task.status.value} · {overdue_days} Tage überfällig",
                    source_route="/content",
                    source_id=str(task.id),
                    priority=priority_value,
                    escalation=priority_value in {"high", "critical"},
                    due_at=task.due_date,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    assignee_username=None,
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
