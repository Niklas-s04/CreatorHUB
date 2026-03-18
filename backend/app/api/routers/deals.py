from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.deal import DealDraft, DealDraftStatus
from app.models.email import EmailThread
from app.models.user import User, UserRole
from app.schemas.deal import DealDraftIntakeRequest, DealDraftOut, DealDraftUpdate
from app.services.deal_intake import extract_deal_intake

router = APIRouter()


def _apply_fields(target: DealDraft, data: dict[str, str | None]) -> None:
    for field, value in data.items():
        setattr(target, field, value)


FIELD_KEYS = [
    "brand_name",
    "contact_name",
    "contact_email",
    "budget",
    "deliverables",
    "usage_rights",
    "deadlines",
    "notes",
]


@router.get("", response_model=list[DealDraftOut])
def list_deal_drafts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    status: DealDraftStatus | None = None,
    thread_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[DealDraftOut]:
    q = db.query(DealDraft)
    if status:
        q = q.filter(DealDraft.status == status)
    if thread_id:
        q = q.filter(DealDraft.thread_id == thread_id)
    safe_limit = max(1, min(limit, 200))
    return q.order_by(DealDraft.created_at.desc()).limit(safe_limit).all()


@router.get("/by-thread/{thread_id}", response_model=DealDraftOut)
def get_deal_by_thread(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DealDraftOut:
    draft = db.query(DealDraft).filter(DealDraft.thread_id == thread_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Deal draft not found for thread")
    return draft


@router.post("/intake", response_model=DealDraftOut)
def create_or_update_deal_from_email(
    payload: DealDraftIntakeRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> DealDraftOut:
    thread = db.query(EmailThread).filter(EmailThread.id == payload.thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Email thread not found")

    draft = db.query(DealDraft).filter(DealDraft.thread_id == thread.id).first()

    extracted: dict[str, str | None] = {}
    if payload.auto_extract or not draft:
        extracted = extract_deal_intake(db, subject=thread.subject, raw_body=thread.raw_body)

    body = {key: extracted.get(key) for key in FIELD_KEYS}

    overrides = payload.model_dump(exclude={"thread_id", "auto_extract", "status"})
    for key in FIELD_KEYS:
        value = overrides.get(key)
        if value is not None:
            body[key] = value

    status = payload.status or (draft.status if draft else DealDraftStatus.intake)

    if draft:
        _apply_fields(draft, body)
        draft.status = status
        db.commit()
        db.refresh(draft)
        return draft

    new_draft = DealDraft(thread_id=thread.id, status=status)
    _apply_fields(new_draft, body)
    db.add(new_draft)
    db.commit()
    db.refresh(new_draft)
    return new_draft


@router.patch("/{deal_id}", response_model=DealDraftOut)
def update_deal_draft(
    deal_id: uuid.UUID,
    payload: DealDraftUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> DealDraftOut:
    draft = db.query(DealDraft).filter(DealDraft.id == deal_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Deal draft not found")

    data = payload.model_dump(exclude_unset=True)
    status = data.pop("status", None)
    for key in FIELD_KEYS:
        if key in data:
            setattr(draft, key, data[key])
    if status:
        draft.status = status
    db.commit()
    db.refresh(draft)
    return draft
