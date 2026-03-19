from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.audit import record_audit_log


def emit_domain_event(
    db: Session,
    *,
    actor: User | None,
    event_name: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any] | None = None,
    description: str | None = None,
) -> None:
    record_audit_log(
        db,
        actor=actor,
        action=f"domain_event.{event_name}",
        entity_type=entity_type,
        entity_id=entity_id,
        description=description or f"Domain event emitted: {event_name}",
        metadata=payload or {},
    )
