from __future__ import annotations

import enum
import uuid
from collections.abc import Mapping, Sequence, Set
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging_config import get_request_id
from app.models.audit import AuditLog
from app.models.user import User

CRITICAL_AUDIT_ACTIONS = {
    "initial_admin_setup_completed",
    "user.role_or_status.update",
    "registration.request.review",
    "auth.session.revoke",
    "auth.mfa.enable",
    "auth.mfa.disable",
    "auth.password.change",
    "auth.password.reset.request",
    "auth.password.reset.confirm",
    "product.delete",
}

SENSITIVE_AUDIT_FIELDS = {
    "password",
    "token",
    "secret",
    "cvv",
    "ssn",
    "mfa_secret",
    "access_token",
    "refresh_token",
    "card_number",
    "card",
}


def _is_sensitive_audit_field(key: object) -> bool:
    lowered = str(key).strip().lower()
    if lowered in SENSITIVE_AUDIT_FIELDS:
        return True
    return any(part in lowered for part in ("password", "token", "secret", "card", "ssn", "cvv"))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _infer_audit_category(action: str, metadata: dict[str, Any] | None) -> str:
    if metadata and isinstance(metadata.get("audit_category"), str):
        return str(metadata["audit_category"])

    lowered = (action or "").strip().lower()
    if lowered.endswith(".approval") or ".approval." in lowered:
        return "approval"
    if lowered.startswith("registration.request"):
        return "approval"
    if lowered.startswith("user.role") or lowered.startswith("user.permission"):
        return "permission_change"
    if lowered.startswith("auth.") or "password" in lowered or "mfa" in lowered:
        return "security"
    if lowered.startswith("email.ai_settings") or lowered.startswith("email.draft."):
        return "ai_action"
    if lowered.startswith("product.workflow"):
        return "approval"
    return "domain"


def _is_critical_audit_action(action: str, metadata: dict[str, Any] | None) -> bool:
    if metadata and "critical" in metadata:
        return bool(metadata.get("critical"))

    lowered = (action or "").strip().lower()
    if action in CRITICAL_AUDIT_ACTIONS:
        return True
    if lowered.startswith("registration.request"):
        return True
    if lowered.startswith("user.role") or lowered.startswith("user.permission"):
        return True
    if lowered.startswith("auth."):
        return True
    return False


def _build_standard_metadata(
    *,
    actor: User | None,
    actor_name: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    base_meta = _normalize(metadata) if metadata else {}
    if not isinstance(base_meta, dict):
        base_meta = {"value": base_meta}

    request_id = base_meta.get("request_id") or get_request_id()
    category = _infer_audit_category(action, base_meta)
    critical = _is_critical_audit_action(action, base_meta)

    base_meta.setdefault("audit_version", "1")
    base_meta.setdefault("audit_category", category)
    base_meta.setdefault("critical", critical)
    base_meta.setdefault("request_id", request_id)
    base_meta.setdefault("actor_id", str(getattr(actor, "id", "")) if actor else None)
    base_meta.setdefault("actor_name", actor_name)
    base_meta.setdefault("action", action)
    base_meta.setdefault("entity_type", entity_type)
    base_meta.setdefault("entity_id", entity_id)
    base_meta.setdefault("occurred_at", _utcnow_iso())
    return base_meta


def _normalize_dict_key(value: Any) -> str:
    normalized = _normalize(value)
    if normalized is None:
        return "null"
    if isinstance(normalized, bool):
        return "true" if normalized else "false"
    if isinstance(normalized, str):
        return normalized
    return str(normalized)


def _normalize(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return _normalize(value.value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {_normalize_dict_key(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(v) for v in value]
    if isinstance(value, Set):
        return [_normalize(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "__iter__"):
        return [_normalize(v) for v in value]
    return str(value)


def redact_audit_data(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_audit_field(key):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_audit_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_audit_data(item) for item in value]
    if isinstance(value, tuple):
        return [redact_audit_data(item) for item in value]
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
    resolved_actor_name = (
        actor_label or getattr(actor, "username", None) or getattr(actor, "email", None)
    )
    normalized_meta = _build_standard_metadata(
        actor=actor,
        actor_name=resolved_actor_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata,
    )

    log = AuditLog(
        actor_id=getattr(actor, "id", None) if actor else None,
        actor_name=resolved_actor_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        before=redact_audit_data(_normalize(before)) if before else None,
        after=redact_audit_data(_normalize(after)) if after else None,
        meta=redact_audit_data(normalized_meta),
    )
    db.add(log)
    return log
