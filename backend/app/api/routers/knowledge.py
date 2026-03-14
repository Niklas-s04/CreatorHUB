from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.models.knowledge import KnowledgeDoc, KnowledgeDocType
from app.models.user import User, UserRole
from app.schemas.knowledge import KnowledgeDocCreate, KnowledgeDocUpdate, KnowledgeDocOut
from app.services.audit import record_audit_log

router = APIRouter()


@router.get("", response_model=list[KnowledgeDocOut])
def list_docs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    type: KnowledgeDocType | None = None,
) -> list[KnowledgeDocOut]:
    q = db.query(KnowledgeDoc)
    if type:
        q = q.filter(KnowledgeDoc.type == type)
    return q.order_by(KnowledgeDoc.updated_at.desc()).all()


@router.post("", response_model=KnowledgeDocOut)
def create_doc(
    payload: KnowledgeDocCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> KnowledgeDocOut:
    doc = KnowledgeDoc(**payload.model_dump())
    db.add(doc)
    db.flush()
    record_audit_log(
        db,
        actor=current_user,
        action="settings.knowledge.create",
        entity_type="knowledge_doc",
        entity_id=str(doc.id),
        description=f"Created knowledge doc '{doc.title}'",
        after={"title": doc.title, "type": doc.type.value},
    )
    db.commit()
    db.refresh(doc)
    return doc


@router.patch("/{doc_id}", response_model=KnowledgeDocOut)
def update_doc(
    doc_id: uuid.UUID,
    payload: KnowledgeDocUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> KnowledgeDocOut:
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    updates = payload.model_dump(exclude_unset=True)
    before: dict[str, str] = {}
    after: dict[str, str] = {}
    for k, v in updates.items():
        current = getattr(doc, k)
        if v == current:
            continue
        before[k] = getattr(current, "value", current)
        setattr(doc, k, v)
        after[k] = getattr(v, "value", v)
    if before:
        record_audit_log(
            db,
            actor=current_user,
            action="settings.knowledge.update",
            entity_type="knowledge_doc",
            entity_id=str(doc.id),
            description=f"Updated knowledge doc '{doc.title}'",
            before=before,
            after=after,
        )
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{doc_id}")
def delete_doc(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> dict:
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    snapshot = {"title": doc.title, "type": doc.type.value}
    record_audit_log(
        db,
        actor=current_user,
        action="settings.knowledge.delete",
        entity_type="knowledge_doc",
        entity_id=str(doc_id),
        description=f"Deleted knowledge doc '{snapshot['title']}'",
        before=snapshot,
    )
    db.delete(doc)
    db.commit()
    return {"deleted": True}
