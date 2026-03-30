from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.knowledge import (
    KnowledgeDoc,
    KnowledgeDocDraftLink,
    KnowledgeDocType,
    KnowledgeDocVersion,
)
from app.models.user import User
from app.models.workflow import WorkflowStatus
from app.schemas.knowledge import KnowledgeDocCreate, KnowledgeDocUpdate
from app.services.audit import record_audit_log
from app.services.errors import BusinessRuleViolation, NotFoundError
from app.services.transactions import transaction_boundary
from app.services.workflow import (
    apply_workflow_change,
    auto_re_review_reason,
    requires_re_review,
    validate_workflow_status_change,
)

KNOWLEDGE_RE_REVIEW_FIELDS: set[str] = {
    "type",
    "title",
    "content",
    "source_name",
    "source_url",
    "source_type",
    "source_review_status",
    "source_review_note",
    "origin_summary",
    "trust_level",
}
KNOWLEDGE_VERSION_FIELDS: set[str] = {
    "type",
    "title",
    "content",
    "workflow_status",
    "review_reason",
    "source_name",
    "source_url",
    "source_type",
    "source_review_status",
    "source_review_note",
    "origin_summary",
    "trust_level",
    "is_outdated",
    "outdated_reason",
    "outdated_at",
}


def get_knowledge_bundle(db: Session) -> dict[str, str]:
    """Return concatenated brand_voice, policy, templates."""
    docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.is_outdated.is_(False)).all()
    parts = {"brand_voice": [], "policy": [], "template": []}
    for d in docs:
        if d.type == KnowledgeDocType.brand_voice:
            parts["brand_voice"].append(f"# {d.title}\n{d.content}")
        elif d.type == KnowledgeDocType.policy:
            parts["policy"].append(f"# {d.title}\n{d.content}")
        elif d.type == KnowledgeDocType.template:
            parts["template"].append(f"# {d.title}\n{d.content}")
    return {
        "brand_voice": "\n\n".join(parts["brand_voice"]).strip(),
        "policy": "\n\n".join(parts["policy"]).strip(),
        "templates": "\n\n".join(parts["template"]).strip(),
    }


def get_knowledge_bundle_with_doc_ids(db: Session) -> tuple[dict[str, str], list[uuid.UUID]]:
    docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.is_outdated.is_(False)).all()
    parts = {"brand_voice": [], "policy": [], "template": []}
    doc_ids: list[uuid.UUID] = []
    for d in docs:
        doc_ids.append(d.id)
        if d.type == KnowledgeDocType.brand_voice:
            parts["brand_voice"].append(f"# {d.title}\n{d.content}")
        elif d.type == KnowledgeDocType.policy:
            parts["policy"].append(f"# {d.title}\n{d.content}")
        elif d.type == KnowledgeDocType.template:
            parts["template"].append(f"# {d.title}\n{d.content}")
    return (
        {
            "brand_voice": "\n\n".join(parts["brand_voice"]).strip(),
            "policy": "\n\n".join(parts["policy"]).strip(),
            "templates": "\n\n".join(parts["template"]).strip(),
        },
        doc_ids,
    )


def _validate_doc_fields(*, title: str | None = None, content: str | None = None) -> None:
    if title is not None and not title.strip():
        raise BusinessRuleViolation("Title must not be empty")
    if content is not None and not content.strip():
        raise BusinessRuleViolation("Content must not be empty")


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _validate_source_and_outdated_fields(
    *,
    source_name: str | None,
    source_url: str | None,
    is_outdated: bool,
    outdated_reason: str | None,
) -> None:
    if source_name is not None and not source_name.strip():
        raise BusinessRuleViolation("Source name must not be empty")
    if source_url is not None and not source_url.strip():
        raise BusinessRuleViolation("Source URL must not be empty")
    if is_outdated and not (outdated_reason or "").strip():
        raise BusinessRuleViolation("Outdated reason is required when marking content outdated")


def _snapshot_doc(
    db: Session,
    *,
    doc: KnowledgeDoc,
    version_number: int,
    actor: User | None,
    change_note: str | None,
) -> None:
    db.add(
        KnowledgeDocVersion(
            knowledge_doc_id=doc.id,
            version_number=version_number,
            type=doc.type,
            title=doc.title,
            content=doc.content,
            workflow_status=doc.workflow_status,
            review_reason=doc.review_reason,
            source_name=doc.source_name,
            source_url=doc.source_url,
            source_type=doc.source_type,
            source_review_status=doc.source_review_status,
            source_review_note=doc.source_review_note,
            origin_summary=doc.origin_summary,
            trust_level=doc.trust_level,
            is_outdated=doc.is_outdated,
            outdated_reason=doc.outdated_reason,
            outdated_at=doc.outdated_at,
            changed_by_id=actor.id if actor else None,
            changed_by_name=actor.username if actor else None,
            change_note=change_note,
        )
    )


def list_docs(db: Session, *, doc_type: KnowledgeDocType | None = None) -> list[KnowledgeDoc]:
    q = db.query(KnowledgeDoc)
    if doc_type:
        q = q.filter(KnowledgeDoc.type == doc_type)
    return q.order_by(KnowledgeDoc.updated_at.desc()).all()


def create_doc(db: Session, *, payload: KnowledgeDocCreate, actor: User | None) -> KnowledgeDoc:
    _validate_doc_fields(title=payload.title, content=payload.content)
    _validate_source_and_outdated_fields(
        source_name=payload.source_name,
        source_url=payload.source_url,
        is_outdated=payload.is_outdated,
        outdated_reason=payload.outdated_reason,
    )
    doc = KnowledgeDoc(
        type=payload.type,
        title=payload.title.strip(),
        content=payload.content.strip(),
        workflow_status=payload.workflow_status,
        review_reason=(payload.review_reason or "").strip() or None,
        source_name=_normalize_optional_text(payload.source_name),
        source_url=_normalize_optional_text(payload.source_url),
        source_type=payload.source_type,
        source_review_status=payload.source_review_status,
        source_review_note=_normalize_optional_text(payload.source_review_note),
        origin_summary=_normalize_optional_text(payload.origin_summary),
        trust_level=payload.trust_level,
        is_outdated=payload.is_outdated,
        outdated_reason=_normalize_optional_text(payload.outdated_reason),
        outdated_at=utcnow() if payload.is_outdated else None,
        current_version=1,
    )
    validate_workflow_status_change(
        current_status=doc.workflow_status,
        target_status=doc.workflow_status,
        review_reason=doc.review_reason,
    )
    with transaction_boundary(db):
        db.add(doc)
        db.flush()
        if doc.workflow_status != WorkflowStatus.draft or doc.review_reason:
            apply_workflow_change(
                entity=doc,
                target_status=doc.workflow_status,
                review_reason=doc.review_reason,
                actor=actor,
            )
        _snapshot_doc(
            db,
            doc=doc,
            version_number=doc.current_version,
            actor=actor,
            change_note="Initial version",
        )
        record_audit_log(
            db,
            actor=actor,
            action="settings.knowledge.create",
            entity_type="knowledge_doc",
            entity_id=str(doc.id),
            description=f"Created knowledge doc '{doc.title}'",
            after={
                "title": doc.title,
                "type": doc.type.value,
                "workflow_status": doc.workflow_status.value,
                "source_review_status": doc.source_review_status.value,
                "trust_level": doc.trust_level.value,
                "is_outdated": doc.is_outdated,
                "current_version": doc.current_version,
            },
        )
    db.refresh(doc)
    return doc


def update_doc(
    db: Session,
    *,
    doc_id: uuid.UUID,
    payload: KnowledgeDocUpdate,
    actor: User | None,
) -> KnowledgeDoc:
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not doc:
        raise NotFoundError("Doc not found")

    updates = payload.model_dump(exclude_unset=True)
    requested_workflow_status = updates.pop("workflow_status", None)
    explicit_review_reason = updates.pop("review_reason", None)
    if "title" in updates and updates["title"] is not None:
        _validate_doc_fields(title=updates["title"])
        updates["title"] = updates["title"].strip()
    if "content" in updates and updates["content"] is not None:
        _validate_doc_fields(content=updates["content"])
        updates["content"] = updates["content"].strip()
    for key in {
        "source_name",
        "source_url",
        "source_review_note",
        "origin_summary",
        "outdated_reason",
    }:
        if key in updates:
            updates[key] = _normalize_optional_text(updates[key])

    next_is_outdated = updates.get("is_outdated", doc.is_outdated)
    next_outdated_reason = updates.get("outdated_reason", doc.outdated_reason)
    _validate_source_and_outdated_fields(
        source_name=updates.get("source_name", doc.source_name),
        source_url=updates.get("source_url", doc.source_url),
        is_outdated=bool(next_is_outdated),
        outdated_reason=next_outdated_reason,
    )

    before: dict[str, str] = {}
    after: dict[str, str] = {}
    previous_review_reason = doc.review_reason

    changed_fields = {key for key in updates.keys() if getattr(doc, key) != updates[key]}
    target_workflow_status = requested_workflow_status or doc.workflow_status
    review_reason = explicit_review_reason
    if requested_workflow_status is None and requires_re_review(
        current_status=doc.workflow_status,
        changed_fields=changed_fields,
        relevant_fields=KNOWLEDGE_RE_REVIEW_FIELDS,
    ):
        target_workflow_status = WorkflowStatus.in_review
        review_reason = review_reason or auto_re_review_reason(changed_fields)

    validate_workflow_status_change(
        current_status=doc.workflow_status,
        target_status=target_workflow_status,
        review_reason=review_reason,
    )

    with transaction_boundary(db):
        for key, value in updates.items():
            current = getattr(doc, key)
            if value == current:
                continue
            before[key] = getattr(current, "value", current)
            setattr(doc, key, value)
            after[key] = getattr(value, "value", value)

        if "is_outdated" in updates:
            if doc.is_outdated and doc.outdated_at is None:
                before["outdated_at"] = None
                doc.outdated_at = utcnow()
                after["outdated_at"] = doc.outdated_at.isoformat()
            if not doc.is_outdated and doc.outdated_at is not None:
                before["outdated_at"] = doc.outdated_at.isoformat()
                doc.outdated_at = None
                after["outdated_at"] = None

        if target_workflow_status != doc.workflow_status:
            before["workflow_status"] = doc.workflow_status.value
            apply_workflow_change(
                entity=doc,
                target_status=target_workflow_status,
                review_reason=review_reason,
                actor=actor,
            )
            after["workflow_status"] = doc.workflow_status.value
            before["review_reason"] = previous_review_reason
            after["review_reason"] = doc.review_reason
        elif explicit_review_reason is not None and explicit_review_reason != doc.review_reason:
            before["review_reason"] = doc.review_reason
            doc.review_reason = explicit_review_reason.strip() or None
            after["review_reason"] = doc.review_reason

        if any(field in before for field in KNOWLEDGE_VERSION_FIELDS):
            doc.current_version += 1
            after["current_version"] = doc.current_version
            _snapshot_doc(
                db,
                doc=doc,
                version_number=doc.current_version,
                actor=actor,
                change_note="Updated knowledge document",
            )
        if before:
            record_audit_log(
                db,
                actor=actor,
                action="settings.knowledge.update",
                entity_type="knowledge_doc",
                entity_id=str(doc.id),
                description=f"Updated knowledge doc '{doc.title}'",
                before=before,
                after=after,
            )
    db.refresh(doc)
    return doc


def delete_doc(db: Session, *, doc_id: uuid.UUID, actor: User | None) -> None:
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not doc:
        raise NotFoundError("Doc not found")
    snapshot = {"title": doc.title, "type": doc.type.value}
    with transaction_boundary(db):
        record_audit_log(
            db,
            actor=actor,
            action="settings.knowledge.delete",
            entity_type="knowledge_doc",
            entity_id=str(doc_id),
            description=f"Deleted knowledge doc '{snapshot['title']}'",
            before=snapshot,
        )
        db.delete(doc)


def link_docs_to_draft(
    db: Session,
    *,
    doc_ids: list[uuid.UUID],
    email_draft_id: uuid.UUID,
    actor: User | None,
) -> None:
    if not doc_ids:
        return

    unique_doc_ids = list(dict.fromkeys(doc_ids))
    existing_rows = (
        db.query(KnowledgeDocDraftLink.knowledge_doc_id)
        .filter(
            KnowledgeDocDraftLink.email_draft_id == email_draft_id,
            KnowledgeDocDraftLink.knowledge_doc_id.in_(unique_doc_ids),
        )
        .all()
    )
    existing_ids = {row[0] for row in existing_rows}
    now = utcnow()
    linked_by = actor.username if actor else "system"
    for doc_id in unique_doc_ids:
        if doc_id in existing_ids:
            continue
        db.add(
            KnowledgeDocDraftLink(
                knowledge_doc_id=doc_id,
                email_draft_id=email_draft_id,
                linked_at=now,
                linked_by_name=linked_by,
            )
        )
