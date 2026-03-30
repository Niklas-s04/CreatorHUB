from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.api.deps import get_db, require_permission
from app.api.querying import apply_sorting, pagination_params, to_page
from app.core.authorization import Permission
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut
from app.schemas.common import Page, SortOrder

router = APIRouter()


def _infer_category(entry: AuditLog) -> str:
    if isinstance(entry.meta, dict):
        category = entry.meta.get("audit_category")
        if isinstance(category, str) and category.strip():
            return category.strip()

    action = (entry.action or "").lower()
    if action.endswith(".approval") or ".approval." in action:
        return "approval"
    if action.startswith("registration.request"):
        return "approval"
    if action.startswith("user.role") or action.startswith("user.permission"):
        return "permission_change"
    if action.startswith("auth.") or "password" in action or "mfa" in action:
        return "security"
    if action.startswith("email.ai_settings") or action.startswith("email.draft."):
        return "ai_action"
    return "domain"


def _is_critical(entry: AuditLog) -> bool:
    if isinstance(entry.meta, dict) and "critical" in entry.meta:
        return bool(entry.meta.get("critical"))
    return _infer_category(entry) in {"approval", "permission_change", "security"}


def _apply_common_filters(
    qry,
    *,
    action: str | None,
    entity_type: str | None,
    entity_id: str | None,
    actor: str | None,
    search: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
):
    if action:
        qry = qry.filter(AuditLog.action == action)
    if entity_type:
        qry = qry.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        qry = qry.filter(AuditLog.entity_id == entity_id)
    if actor:
        pattern = f"%{actor}%"
        qry = qry.filter(AuditLog.actor_name.ilike(pattern))
    if search:
        pattern = f"%{search}%"
        qry = qry.filter(
            or_(
                AuditLog.description.ilike(pattern),
                AuditLog.action.ilike(pattern),
                AuditLog.entity_type.ilike(pattern),
            )
        )
    if created_from is not None:
        qry = qry.filter(AuditLog.created_at >= created_from)
    if created_to is not None:
        qry = qry.filter(AuditLog.created_at <= created_to)
    return qry


def _post_filter_items(
    items: list[AuditLog],
    *,
    category: str | None,
    critical_only: bool,
) -> list[AuditLog]:
    out = items
    if category:
        out = [item for item in out if _infer_category(item) == category]
    if critical_only:
        out = [item for item in out if _is_critical(item)]
    return out


@router.get("", response_model=Page[AuditLogOut])
def list_audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.audit_view)),
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor: str | None = None,
    search: str | None = None,
    category: str | None = None,
    critical_only: bool = False,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[AuditLogOut]:
    limit, offset, sort_by, sort_order = paging
    qry = db.query(AuditLog)
    qry = _apply_common_filters(
        qry,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        search=search,
        created_from=created_from,
        created_to=created_to,
    )

    qry, selected_sort, selected_order = apply_sorting(
        qry,
        model=AuditLog,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={"created_at", "action", "entity_type", "actor_name"},
        fallback="created_at",
    )

    items_all = qry.all()
    filtered_all = _post_filter_items(items_all, category=category, critical_only=critical_only)
    total = len(filtered_all)
    items = filtered_all[offset : offset + limit]

    return to_page(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=selected_sort,
        sort_order=selected_order,
    )


@router.get("/export/csv")
def export_audit_logs_csv(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.audit_view)),
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor: str | None = None,
    search: str | None = None,
    category: str | None = None,
    critical_only: bool = False,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> StreamingResponse:
    qry = db.query(AuditLog)
    qry = _apply_common_filters(
        qry,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        search=search,
        created_from=created_from,
        created_to=created_to,
    )
    items = _post_filter_items(
        qry.order_by(AuditLog.created_at.desc()).all(),
        category=category,
        critical_only=critical_only,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "created_at",
            "actor_name",
            "action",
            "entity_type",
            "entity_id",
            "category",
            "critical",
            "description",
            "before",
            "after",
            "meta",
        ]
    )

    for row in items:
        writer.writerow(
            [
                str(row.id),
                row.created_at.isoformat() if row.created_at else "",
                row.actor_name or "system",
                row.action,
                row.entity_type,
                row.entity_id or "",
                _infer_category(row),
                "true" if _is_critical(row) else "false",
                row.description or "",
                json.dumps(row.before or {}, ensure_ascii=True),
                json.dumps(row.after or {}, ensure_ascii=True),
                json.dumps(row.meta or {}, ensure_ascii=True),
            ]
        )

    content = buffer.getvalue()
    filename = f"audit-export-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([content]), media_type="text/csv; charset=utf-8", headers=headers)
