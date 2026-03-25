from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeDoc, KnowledgeDocType
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

KNOWLEDGE_RE_REVIEW_FIELDS: set[str] = {"type", "title", "content"}


def get_knowledge_bundle(db: Session) -> dict[str, str]:
    """Return concatenated brand_voice, policy, templates."""
    docs = db.query(KnowledgeDoc).all()
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


def _validate_doc_fields(*, title: str | None = None, content: str | None = None) -> None:
    if title is not None and not title.strip():
        raise BusinessRuleViolation("Title must not be empty")
    if content is not None and not content.strip():
        raise BusinessRuleViolation("Content must not be empty")


def list_docs(db: Session, *, doc_type: KnowledgeDocType | None = None) -> list[KnowledgeDoc]:
    q = db.query(KnowledgeDoc)
    if doc_type:
        q = q.filter(KnowledgeDoc.type == doc_type)
    return q.order_by(KnowledgeDoc.updated_at.desc()).all()


def create_doc(db: Session, *, payload: KnowledgeDocCreate, actor: User | None) -> KnowledgeDoc:
    _validate_doc_fields(title=payload.title, content=payload.content)
    doc = KnowledgeDoc(
        type=payload.type,
        title=payload.title.strip(),
        content=payload.content.strip(),
        workflow_status=payload.workflow_status,
        review_reason=(payload.review_reason or "").strip() or None,
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
