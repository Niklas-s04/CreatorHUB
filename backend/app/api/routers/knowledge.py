from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import (
    SensitiveActionContext,
    get_current_user,
    get_db,
    require_permission,
    require_sensitive_action,
)
from app.api.querying import apply_sorting, pagination_params, to_page
from app.core.authorization import Permission
from app.models.knowledge import KnowledgeDoc, KnowledgeDocType
from app.models.user import User
from app.schemas.common import Page, SortOrder
from app.schemas.knowledge import KnowledgeDocCreate, KnowledgeDocOut, KnowledgeDocUpdate
from app.services import knowledge_service
from app.services.errors import BusinessRuleViolation, NotFoundError

router = APIRouter()


@router.get("", response_model=Page[KnowledgeDocOut])
def list_docs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    type: KnowledgeDocType | None = None,
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[KnowledgeDocOut]:
    limit, offset, sort_by, sort_order = paging
    qry = db.query(KnowledgeDoc)
    if type:
        qry = qry.filter(KnowledgeDoc.type == type)

    total = qry.order_by(None).count()
    qry, selected_sort, selected_order = apply_sorting(
        qry,
        model=KnowledgeDoc,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={"created_at", "updated_at", "title", "type"},
        fallback="updated_at",
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


@router.post("", response_model=KnowledgeDocOut)
def create_doc(
    payload: KnowledgeDocCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.knowledge_manage)),
) -> KnowledgeDocOut:
    try:
        return knowledge_service.create_doc(db, payload=payload, actor=current_user)
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{doc_id}", response_model=KnowledgeDocOut)
def update_doc(
    doc_id: uuid.UUID,
    payload: KnowledgeDocUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.knowledge_manage)),
) -> KnowledgeDocOut:
    try:
        return knowledge_service.update_doc(db, doc_id=doc_id, payload=payload, actor=current_user)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{doc_id}")
def delete_doc(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.knowledge_manage)),
    _: SensitiveActionContext = Depends(require_sensitive_action("knowledge.doc.delete")),
) -> dict:
    try:
        knowledge_service.delete_doc(db, doc_id=doc_id, actor=current_user)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}
