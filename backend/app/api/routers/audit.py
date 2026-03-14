from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit import AuditLogOut

router = APIRouter()


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLogOut]:
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
    return qry.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
