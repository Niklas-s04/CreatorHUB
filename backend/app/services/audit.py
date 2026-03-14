from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return enum_value
    return value


def record_audit_log(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    description: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    actor_label: str | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=getattr(actor, "id", None) if actor else None,
        actor_name=actor_label or getattr(actor, "username", None) or getattr(actor, "email", None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        before=_normalize(before) if before else None,
        after=_normalize(after) if after else None,
        meta=_normalize(metadata) if metadata else None,
    )
    db.add(log)
    return log
