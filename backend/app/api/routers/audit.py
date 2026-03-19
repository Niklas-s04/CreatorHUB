from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.api.querying import apply_sorting, pagination_params, to_page
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit import AuditLogOut
from app.schemas.common import Page, SortOrder

router = APIRouter()


@router.get("", response_model=Page[AuditLogOut])
def list_audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor: str | None = None,
    search: str | None = None,
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[AuditLogOut]:
    limit, offset, sort_by, sort_order = paging
    qry = db.query(AuditLog)
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

    total = qry.order_by(None).count()
    qry, selected_sort, selected_order = apply_sorting(
        qry,
        model=AuditLog,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={"created_at", "action", "entity_type", "actor_name"},
        fallback="created_at",
    )
    items = qry.offset(offset).limit(limit).all()
    return to_page(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=selected_sort,
        sort_order=selected_order,
    )
